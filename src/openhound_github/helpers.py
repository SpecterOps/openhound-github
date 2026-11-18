import logging
import random
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
from openhound_github.github_rest_client import GraphQLPageRetryBudget
from openhound_github.github_retry import (
    is_primary_rate_limit_response,
    is_secondary_rate_limit_response,
)

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_REST_API_URL = "https://api.github.com"
DEFAULT_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def _rest_api_url(client: RESTClient) -> str:
    """Normalize the client's REST base URL, defaulting missing or blank values."""
    base_url = getattr(client, "base_url", None)
    return (
        str(base_url or DEFAULT_GITHUB_REST_API_URL).strip().rstrip("/")
        or DEFAULT_GITHUB_REST_API_URL
    )


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


def graphql_repository_batches(
    client: RESTClient,
    *,
    query: str,
    repository_ids: list[str],
    graphql_path: str = "/graphql",
    org_name: str,
    repository_names: dict[str, str] | None = None,
    batch_size: int = 50,
    initial_branch_count: int = 50,
    log: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Fetch explicit IDs, splitting failed batches while retaining good nodes.

    Gateway failures split batches larger than 25 immediately. At 25 or fewer
    IDs, allow two delayed retries before isolating failures by bisection.
    Descendants of an exhausted batch get one gateway attempt each, bounding
    recovery work during a sustained outage. HTTP retries for other transient
    failures, rate limits, and credential refresh retain their existing policy.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be an integer between 1 and 100")
    if type(initial_branch_count) is not int or not 1 <= initial_branch_count <= 100:
        raise ValueError("initial_branch_count must be an integer between 1 and 100")
    batch_logger = log or logger
    names = repository_names or {}
    stats = {
        "initial_batches": 0, "batch_attempts": 0, "failed_batch_attempts": 0,
        "splits": 0, "successful_initial_batches": 0, "recovered_initial_batches": 0,
        "incomplete_initial_batches": 0, "emitted_repositories": 0,
        "request_seconds": 0.0,
    }
    unresolved_ids: set[str] = set()

    def request_finished(started: float, attempt_id: int, status: int | None,
                         outcome: str, error_type: str | None = None) -> None:
        elapsed = time.monotonic() - started
        stats["request_seconds"] += elapsed
        batch_logger.debug(
            "GraphQL repository batch request finished: organization=%s batch=%d "
            "attempt=%d outcome=%s HTTP=%s duration_seconds=%.3f error_type=%s",
            org_name, stats["initial_batches"], attempt_id, outcome, status, elapsed, error_type,
            extra={"resource": "repositories_graphql", "org_name": org_name,
                   "batch_number": stats["initial_batches"], "batch_attempt": attempt_id,
                   "http_status": status, "duration_seconds": elapsed,
                   "outcome": outcome, "error_type": error_type},
        )

    def gap(ids: list[str], reason: str) -> None:
        unresolved_ids.update(ids)
        batch_logger.error(
            "GraphQL repository collection gap for organization '%s': %s; "
            "unresolved repositories: %s; continuing remaining batches",
            org_name,
            reason,
            [names.get(node_id) or node_id for node_id in ids],
            extra={
                "resource": "repositories_graphql",
                "phase": "resource_iteration",
                "org_name": org_name,
                "repository_ids": ids,
            },
        )

    def collect(ids: list[str], allow_gateway_retries: bool = True):
        budget = GraphQLPageRetryBudget()
        for attempt in range(3 if len(ids) <= 25 and allow_gateway_retries else 1):
            stats["batch_attempts"] += 1
            attempt_id = stats["batch_attempts"]
            batch_logger.debug(
                "GraphQL repository batch request started: organization=%s batch=%d "
                "attempt=%d size=%d initial_branch_count=%d repository_ids=%s repositories=%s",
                org_name, stats["initial_batches"], attempt_id, len(ids), initial_branch_count,
                ids, [names.get(node_id) or node_id for node_id in ids],
                extra={"resource": "repositories_graphql", "org_name": org_name,
                       "batch_number": stats["initial_batches"], "batch_attempt": attempt_id,
                       "batch_size": len(ids), "initial_branch_count": initial_branch_count,
                       "repository_ids": ids},
            )
            started = time.monotonic()
            response = None
            try:
                with budget.activate():
                    response = client.post(
                        graphql_path, json={"query": query, "variables": {"ids": ids, "branch_count": initial_branch_count}}
                    )
                response.raise_for_status()
                payload = response.json()
                request_finished(started, attempt_id, response.status_code, "response")
                break
            except Exception as error:
                stats["failed_batch_attempts"] += 1
                error_response = getattr(error, "response", None)
                status = getattr(error_response if error_response is not None else response, "status_code", None)
                request_finished(started, attempt_id, status, "failed", type(error).__name__)
                gateway = _graphql_gateway_status(error)
                if (
                    gateway is not None
                    and len(ids) <= 25
                    and allow_gateway_retries
                    and attempt < 2
                ):
                    budget.max_failures = budget.failures + 1
                    delay = random.uniform(1, 2) if attempt == 0 else 15
                    batch_logger.warning(
                        "Retrying GraphQL repository batch of %d for organization '%s' "
                        "in %.2f seconds after HTTP %d",
                        len(ids),
                        org_name,
                        delay,
                        gateway,
                    )
                    time.sleep(delay)
                    continue
                if gateway is not None and len(ids) > 1:
                    batch_logger.warning(
                        "Splitting failed GraphQL repository batch of %d for organization '%s' after HTTP %d",
                        len(ids),
                        org_name,
                        gateway,
                    )
                    stats["splits"] += 1
                    midpoint = len(ids) // 2
                    retry_children = allow_gateway_retries and len(ids) > 25
                    yield from collect(ids[:midpoint], retry_children)
                    yield from collect(ids[midpoint:], retry_children)
                else:
                    gap(ids, f"{type(error).__name__}: {error}")
                return

        if not isinstance(payload, dict):
            stats["failed_batch_attempts"] += 1
            gap(ids, "GraphQL response must be an object")
            return
        data = payload.get("data")
        nodes = data.get("nodes") if isinstance(data, dict) else None
        errors = payload.get("errors") or []
        # Never accept a repository whose nested metadata has a GraphQL error.
        failed_indices = set()
        unscoped_error = False
        for error in errors:
            path = error.get("path") or []
            if len(path) >= 2 and path[0] == "nodes" and isinstance(path[1], int):
                failed_indices.add(path[1])
            else:
                unscoped_error = True
        returned: dict[str, dict[str, Any]] = {}
        if isinstance(nodes, list) and not unscoped_error:
            for index, node in enumerate(nodes):
                if (
                    index not in failed_indices
                    and isinstance(node, dict)
                    and node.get("id") in ids
                ):
                    returned[node["id"]] = node
        for node_id in ids:
            if node_id in returned:
                yield returned[node_id]
        missing = [node_id for node_id in ids if node_id not in returned]
        batch_logger.debug(
            "GraphQL repository batch result: organization=%s batch=%d attempt=%d "
            "returned=%d unresolved=%d",
            org_name, stats["initial_batches"], attempt_id, len(returned), len(missing),
        )
        if missing:
            stats["failed_batch_attempts"] += 1
            if len(ids) == 1:
                gap(missing, "missing, inaccessible, or incomplete GraphQL node")
            else:
                # Retry only unresolved IDs; already emitted results are retained.
                stats["splits"] += int(len(missing) > 1)
                midpoint = max(1, len(missing) // 2)
                yield from collect(missing[:midpoint], False)
                if missing[midpoint:]:
                    yield from collect(missing[midpoint:], False)

    unique_ids = list(dict.fromkeys(repository_ids))
    for start in range(0, len(unique_ids), batch_size):
        stats["initial_batches"] += 1
        batch_ids = unique_ids[start : start + batch_size]
        attempts_before = stats["batch_attempts"]
        emitted = 0
        for row in collect(batch_ids):
            emitted += 1
            stats["emitted_repositories"] += 1
            yield row
        if emitted != len(batch_ids):
            stats["incomplete_initial_batches"] += 1
        elif stats["batch_attempts"] - attempts_before > 1:
            stats["recovered_initial_batches"] += 1
        else:
            stats["successful_initial_batches"] += 1

    batch_logger.info(
        "GraphQL repository collection summary for organization '%s': "
        "requested=%d emitted=%d unresolved=%d initial_batches=%d "
        "successful_initial_batches=%d recovered_initial_batches=%d "
        "incomplete_initial_batches=%d batch_attempts=%d failed_batch_attempts=%d "
        "splits=%d request_seconds=%.3f",
        org_name, len(unique_ids), stats["emitted_repositories"], len(unresolved_ids),
        stats["initial_batches"], stats["successful_initial_batches"],
        stats["recovered_initial_batches"], stats["incomplete_initial_batches"],
        stats["batch_attempts"], stats["failed_batch_attempts"], stats["splits"],
        stats["request_seconds"],
        extra={"resource": "repositories_graphql", "org_name": org_name,
               "requested_repositories": len(unique_ids),
               "unresolved_repositories": len(unresolved_ids), **stats},
    )


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

    HTTP retries and smaller-page recovery share three transient attempts per
    page. Gateway failures at the smallest size receive up to two additional
    attempts with backoff. Rate-limit and credential-refresh retries retain
    their existing policy.
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
                page_size for page_size in page_sizes if page_size <= stable_page_size
            )
            probing_base_page_size = True
        else:
            candidate_sizes = tuple(
                page_size for page_size in page_sizes if page_size <= stable_page_size
            )
            probing_base_page_size = False

        page_data: dict[str, Any] | None = None
        paginator: GraphQLCursorPaginator | None = None
        successful_page_size: int | None = None
        retry_budget = GraphQLPageRetryBudget()

        # Reserve two retries for gateway failures at the smallest size, even
        # when shrinking the connection consumed the shared transient budget.
        attempt_sizes = candidate_sizes + (page_sizes[-1],) * 2
        smallest_size_retries = 0
        for index, page_size in enumerate(attempt_sizes):
            request_variables = {
                **variables,
                cursor_variable: cursor,
                page_size_variable: page_size,
            }
            try:
                with retry_budget.activate():
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
                retry_smallest_size = (
                    status_code is not None
                    and page_size == page_sizes[-1]
                    and smallest_size_retries < 2
                )
                next_page_size = (
                    attempt_sizes[index + 1]
                    if (
                        status_code is not None
                        and index + 1 < len(attempt_sizes)
                        and (not retry_budget.exhausted or retry_smallest_size)
                    )
                    else None
                )
                if next_page_size is not None:
                    if retry_smallest_size:
                        smallest_size_retries += 1
                        # Each reserved attempt can issue only one additional
                        # transient send through the HTTP retry layer.
                        retry_budget.max_failures = retry_budget.failures + 1
                        delay = (
                            random.uniform(1, 2) if smallest_size_retries == 1 else 15
                        )
                        time.sleep(delay)
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


def _response_request_label(response: requests.Response) -> str:
    """Identify a request by method and path without logging its query string."""
    request = response.request
    if request is None or not request.url:
        return "unknown request"
    return f"{request.method or 'UNKNOWN'} {urlparse(request.url).path}"


def _is_credential_export_creation_response(response: requests.Response) -> bool:
    """Identify a POST that starts an enterprise credential export."""
    request = response.request
    if request is None or request.method != "POST" or not request.url:
        return False
    path = urlparse(request.url).path.rstrip("/")
    return "/enterprises/" in path and path.endswith("/credentials/exports")


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
                    "Primary rate limit reached for %s, retrying in %s seconds",
                    _response_request_label(response),
                    delay,
                )
                return True
            return False

        if response.status_code not in (403, 429):
            return False

        if _is_credential_export_creation_response(response) and (
            response.status_code == 429
            or bool(headers.get("Retry-After"))
            or is_primary_rate_limit_response(response)
            or is_secondary_rate_limit_response(response)
        ):
            logger.warning(
                "Rate limit reached for %s; skipping export creation retry",
                _response_request_label(response),
            )
            return False

        if is_primary_rate_limit_response(response):
            reset_at = headers.get("x-ratelimit-reset")
            delay = int(reset_at) - now if reset_at else 0
            headers["Retry-After"] = str(delay)
            logger.warning(
                "Primary rate limit reached for %s, retrying in %s seconds",
                _response_request_label(response),
                delay,
            )
            return True

        if is_secondary_rate_limit_response(response):
            logger.warning(
                "Secondary rate limit reached for %s, retrying in 60 seconds",
                _response_request_label(response),
            )
            headers["Retry-After"] = "60"
            return True

        if headers.get("Retry-After"):
            return True

        return False

    return retry_policy
