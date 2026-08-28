import logging
import time
from typing import Optional, overload
from urllib.parse import urlparse

from dlt.common import jsonpath
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    JSONResponseCursorPaginator,
)
from requests import Request

from openhound_github.auth import GitHubAppInstallationAuth

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_REST_API_URL = "https://api.github.com"
DEFAULT_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


class GraphQLPaginationError(RuntimeError):
    pass


@overload
def graphql_client_and_path(
    rest_client: RESTClient,
    graphql_client: RESTClient | None,
) -> tuple[RESTClient, str]: ...


@overload
def graphql_client_and_path(
    rest_client: RESTClient | None,
    graphql_client: RESTClient | None,
) -> tuple[RESTClient | None, str]: ...


def graphql_client_and_path(
    rest_client: RESTClient | None,
    graphql_client: RESTClient | None,
) -> tuple[RESTClient | None, str]:
    """Return the configured GraphQL client and its request path."""
    if graphql_client:
        return graphql_client, ""
    return rest_client, "/graphql"


def scim_skip_reason(exception: BaseException) -> str | None:
    """Return a user-facing reason for expected SCIM API unavailability."""
    if not isinstance(exception, requests.HTTPError) or exception.response is None:
        return None

    status_code = exception.response.status_code
    if status_code in (401, 403):
        return "the configured credentials do not have SCIM access"
    if status_code == 404:
        return "the GitHub scope does not expose SCIM endpoints"
    return None


class GraphQLCursorPaginator(JSONResponseCursorPaginator):
    def __init__(
        self,
        page_info_path: str,
        cursor_variable: str = "after",
        cursor_field: str = "endCursor",
        has_next_field: str = "hasNextPage",
        allow_missing_page_info: bool = False,
    ) -> None:

        super().__init__(
            cursor_path=f"{page_info_path}.{cursor_field}",  # Path to extract cursor
            cursor_param=None,
            cursor_body_path=None,  # We'll handle this manually in update_request
            stop_after_empty_page=False,
            has_more_path=f"{page_info_path}.{has_next_field}",  # Path to hasNextPage boolean
        )
        self.page_info_path = page_info_path
        self.cursor_variable = cursor_variable
        self.cursor_field = cursor_field
        self.has_next_field = has_next_field
        self.allow_missing_page_info = allow_missing_page_info

    def init_request(self, request: "Request") -> None:
        self._next_reference = None
        self._has_next_page = True

    def update_state(self, response, data=None):
        response_json = response.json()
        errors = response_json.get("errors")
        if errors:
            messages = []
            for error in errors:
                if isinstance(error, dict):
                    message = error.get("message", "unknown GraphQL error")
                    extensions = error.get("extensions") or {}
                    error_type = error.get("type") or extensions.get("type")
                    path = error.get("path")
                    details = message
                    if error_type:
                        details = f"{details} ({error_type})"
                    if path:
                        details = f"{details} at {path}"
                    messages.append(details)
                else:
                    messages.append(str(error))
            raise GraphQLPaginationError(
                f"GraphQL response contained errors while reading {self.page_info_path}: "
                + "; ".join(messages)
            )

        self._normalize_page_info(data)

        page_info = jsonpath.find_values(self.page_info_path, response_json)

        if not page_info:
            if not self.allow_missing_page_info:
                raise GraphQLPaginationError(
                    f"GraphQL pageInfo not found at {self.page_info_path}"
                )
            self._next_reference = None
            self._has_next_page = False
            return

        page_info_obj = page_info[0]
        cursor = page_info_obj.get(self.cursor_field)
        has_next = page_info_obj.get(self.has_next_field)

        if not isinstance(has_next, bool):
            raise GraphQLPaginationError(
                f"GraphQL {self.page_info_path}.{self.has_next_field} must be a bool"
            )
        if has_next and not cursor:
            raise GraphQLPaginationError(
                f"GraphQL {self.page_info_path}.{self.cursor_field} is required when "
                f"{self.has_next_field} is true"
            )

        self._next_reference = cursor
        self._has_next_page = has_next

    def _normalize_page_info(self, data):
        if isinstance(data, list):
            for item in data:
                self._normalize_page_info(item)
            return

        if not isinstance(data, dict):
            return

        page_info = data.get("pageInfo")
        if isinstance(page_info, dict):
            has_next = page_info.get(self.has_next_field)
            if has_next is False and self.cursor_field not in page_info:
                page_info[self.cursor_field] = None

        for value in data.values():
            self._normalize_page_info(value)

    def update_request(self, request: "Request") -> None:
        if not self._has_next_page:
            return

        if not self._next_reference:
            raise GraphQLPaginationError(
                f"GraphQL cursor is missing for variable {self.cursor_variable}"
            )
        if not isinstance(request.json, dict):
            raise GraphQLPaginationError("GraphQL request body must be a JSON object")
        variables = request.json.get("variables")
        if not isinstance(variables, dict):
            raise GraphQLPaginationError("GraphQL request body must contain variables")

        variables[self.cursor_variable] = self._next_reference


def _response_message(response: requests.Response) -> str:
    try:
        response_data = response.json()
    except ValueError:
        return getattr(response, "text", "")
    if isinstance(response_data, dict):
        return response_data.get("message", "")
    return ""


def _has_graphql_errors(response: requests.Response) -> bool:
    try:
        response_data = response.json()
    except ValueError:
        return False
    return isinstance(response_data, dict) and bool(response_data.get("errors"))


def _has_invalid_json_body(response: requests.Response) -> bool:
    try:
        response.json()
    except ValueError:
        return True
    return False


def _is_graphql_response(response: requests.Response) -> bool:
    if response.headers.get("x-ratelimit-resource") == "graphql":
        return True

    request = response.request
    if request is None or not request.url:
        return False

    return urlparse(request.url).path.rstrip("/").endswith("/graphql")


def github_retry_policy(auth: AuthConfigBase):
    def retry_policy(
        response: Optional[requests.Response], exception: Optional[BaseException]
    ) -> bool:
        if response is None:
            return False

        headers = response.headers
        now = int(time.time())

        # DLT retries the same prepared request after long Retry-After sleeps.
        if (
            response.status_code == 401
            and "bad credentials" in _response_message(response).lower()
            and isinstance(auth, GitHubAppInstallationAuth)
            and response.request is not None
        ):
            if not auth.refresh_request(response.request):
                return False
            logger.warning(
                "GitHub App installation token rejected, retrying request with refreshed token"
            )
            return True

        if (
            response.status_code == 200
            and _is_graphql_response(response)
            and _has_invalid_json_body(response)
        ):
            logger.warning("GraphQL response body was not valid JSON, retrying request")
            return True

        if (
            response.status_code == 200
            and _is_graphql_response(response)
            and _has_graphql_errors(response)
        ):
            if headers.get("Retry-After"):
                return True

            if headers.get("x-ratelimit-remaining") == "0":
                reset_at = headers.get("x-ratelimit-reset")
                delay = int(reset_at) - now if reset_at else 0
                headers["Retry-After"] = str(delay)
                logger.warning(
                    "Primary rate limit reached, retrying in %s seconds", delay
                )
                return True
            return False

        if response.status_code not in (403, 429):
            return False

        message = _response_message(response).lower()
        if (
            headers.get("x-ratelimit-remaining") == "0"
            or "api rate limit exceeded" in message
        ):
            reset_at = headers.get("x-ratelimit-reset")
            delay = int(reset_at) - now if reset_at else 0
            headers["Retry-After"] = str(delay)
            logger.warning("Primary rate limit reached, retrying in %s seconds", delay)
            return True

        if "secondary rate limit" in message or "abuse detection" in message:
            logger.warning("Secondary rate limit reached, retrying in 60 seconds")
            headers["Retry-After"] = "60"
            return True

        if headers.get("Retry-After"):
            return True

        return False

    return retry_policy
