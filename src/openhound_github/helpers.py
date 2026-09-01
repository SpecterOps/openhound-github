import logging
import time
from collections.abc import Iterator
from typing import Any, Optional, overload
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
from openhound_github.github_retry import (
    is_primary_rate_limit_response,
    is_secondary_rate_limit_response,
)

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


class AdaptiveGraphQLPageError(RuntimeError):
    """A terminal GraphQL page failure with adaptive pagination context."""

    def __init__(
        self,
        *,
        cursor: str | None,
        page_size: int,
        error: BaseException,
    ) -> None:
        super().__init__(str(error))
        self.cursor = cursor
        self.page_size = page_size
        self.error = error


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

    @property
    def next_cursor(self) -> str | None:
        return self._next_reference

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


def _graphql_gateway_status(exception: BaseException) -> int | None:
    if not isinstance(exception, requests.HTTPError) or exception.response is None:
        return None

    status_code = exception.response.status_code
    if status_code in (502, 504):
        return status_code
    return None


def adaptive_graphql_paginate(
    client: RESTClient,
    *,
    graphql_path: str = "/graphql",
    query: str,
    variables: dict[str, Any],
    page_info_path: str,
    cursor_variable: str = "after",
    page_size_variable: str = "count",
    page_sizes: tuple[int, ...] = (100, 50, 25),
    allow_missing_page_info: bool = False,
    resource_name: str = "graphql",
    scope_name: str | None = None,
    scope_value: str | None = None,
    log: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield GraphQL pages while adapting connection size after gateway failures.

    The underlying HTTP session still owns ordinary request retries. This helper
    handles the remaining terminal 502/504 case by retrying the same cursor with
    progressively smaller connection sizes.
    """
    if not page_sizes or any(page_size <= 0 for page_size in page_sizes):
        raise ValueError("page_sizes must contain positive integers")
    if tuple(sorted(set(page_sizes), reverse=True)) != page_sizes:
        raise ValueError("page_sizes must be unique and in descending order")

    logger_instance = log or logger
    base_page_size = page_sizes[0]
    cursor = variables.get(cursor_variable)
    if cursor is not None and not isinstance(cursor, str):
        raise ValueError(f"{cursor_variable} must be a string or None")

    stable_page_size = base_page_size
    probe_base_page_size = False

    while True:
        if stable_page_size == base_page_size:
            candidate_sizes = page_sizes
            probing_base_page_size = False
        elif probe_base_page_size:
            candidate_sizes = (base_page_size,) + tuple(
                page_size
                for page_size in page_sizes
                if page_size <= stable_page_size
            )
            probing_base_page_size = True
        else:
            candidate_sizes = tuple(
                page_size
                for page_size in page_sizes
                if page_size <= stable_page_size
            )
            probing_base_page_size = False

        page_data: dict[str, Any] | None = None
        paginator: GraphQLCursorPaginator | None = None
        successful_page_size: int | None = None

        for index, page_size in enumerate(candidate_sizes):
            request_variables = {
                **variables,
                cursor_variable: cursor,
                page_size_variable: page_size,
            }
            try:
                response = client.post(
                    graphql_path,
                    json={"query": query, "variables": request_variables},
                )
                response.raise_for_status()
                response_json = response.json()
                paginator = GraphQLCursorPaginator(
                    page_info_path=page_info_path,
                    cursor_variable=cursor_variable,
                    cursor_field="endCursor",
                    has_next_field="hasNextPage",
                    allow_missing_page_info=allow_missing_page_info,
                )
                paginator.update_state(response)
                page_data = response_json.get("data")
                if not isinstance(page_data, dict):
                    raise GraphQLPaginationError(
                        "GraphQL response data must be an object"
                    )
                successful_page_size = page_size
                break
            except Exception as error:
                status_code = _graphql_gateway_status(error)
                next_page_size = (
                    candidate_sizes[index + 1]
                    if status_code is not None and index + 1 < len(candidate_sizes)
                    else None
                )
                if next_page_size is not None:
                    scope = (
                        f" {scope_name} '{scope_value}'"
                        if scope_name and scope_value
                        else ""
                    )
                    logger_instance.warning(
                        "Adaptive GraphQL pagination for resource '%s'%s retrying "
                        "cursor %r with page size %d after HTTP %d at page size %d",
                        resource_name,
                        scope,
                        cursor,
                        next_page_size,
                        status_code,
                        page_size,
                    )
                    continue
                raise AdaptiveGraphQLPageError(
                    cursor=cursor,
                    page_size=page_size,
                    error=error,
                ) from error

        if page_data is None or paginator is None or successful_page_size is None:
            raise GraphQLPaginationError("GraphQL page did not produce data")

        yield page_data

        if successful_page_size == base_page_size:
            stable_page_size = base_page_size
            probe_base_page_size = False
        elif stable_page_size == base_page_size:
            stable_page_size = successful_page_size
            probe_base_page_size = True
        elif probing_base_page_size:
            stable_page_size = successful_page_size
            probe_base_page_size = False
        elif successful_page_size < stable_page_size:
            stable_page_size = successful_page_size
            probe_base_page_size = False

        if not paginator.has_next_page:
            break

        cursor = paginator.next_cursor


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

        if is_primary_rate_limit_response(response):
            reset_at = headers.get("x-ratelimit-reset")
            delay = int(reset_at) - now if reset_at else 0
            headers["Retry-After"] = str(delay)
            logger.warning("Primary rate limit reached, retrying in %s seconds", delay)
            return True

        if is_secondary_rate_limit_response(response):
            logger.warning("Secondary rate limit reached, retrying in 60 seconds")
            headers["Retry-After"] = "60"
            return True

        if headers.get("Retry-After"):
            return True

        return False

    return retry_policy
