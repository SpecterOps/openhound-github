from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

from dlt.sources.helpers import requests
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout
from tenacity import RetryCallState
from tenacity.stop import stop_base

from openhound_github.github_retry import should_retry_github_response

__all__ = ["github_http_session", "should_retry_github_response"]


@dataclass
class GraphQLPageRetryBudget:
    """Share transient failures across page sizes without changing other requests."""

    failures: int = 0

    @property
    def exhausted(self) -> bool:
        return self.failures >= 3

    @contextmanager
    def activate(self):
        token = _graphql_page_budget.set(self)
        try:
            yield
        finally:
            _graphql_page_budget.reset(token)


_graphql_page_budget: ContextVar[GraphQLPageRetryBudget | None] = ContextVar(
    "github_graphql_page_budget", default=None
)


class _StopAfterTransientFailures(stop_base):
    """Count transient failures per send, independently of other retry reasons."""

    def __call__(self, retry_state: RetryCallState) -> bool:
        outcome = retry_state.outcome
        if outcome is None:
            return False
        exception = outcome.exception()
        response = None
        if isinstance(exception, requests.HTTPError):
            response = exception.response
        elif exception is None:
            response = outcome.result()
        transient = isinstance(exception, (ConnectionError, Timeout, ChunkedEncodingError)) or (
            response is not None and 500 <= response.status_code < 600
        )
        page_budget = _graphql_page_budget.get()
        if page_budget is not None:
            page_budget.failures += int(transient)
            # Return gateway errors immediately so pagination can shrink the page.
            return page_budget.exhausted or (
                response is not None and response.status_code in (502, 504)
            )
        failures = getattr(retry_state, "_github_transient_failures", 0) + int(transient)
        setattr(retry_state, "_github_transient_failures", failures)
        return failures >= 3


def github_http_session(retry_condition):
    """Bound transient failures while retaining DLT's existing retry policy."""
    session = requests.Client(
        request_timeout=(10, 30),
        status_codes=tuple(range(500, 600)),
        retry_condition=retry_condition,
    ).session
    # Keep the configured overall limit for rate limits and credential refresh.
    # RetryCallState is new for every send, including concurrent requests.
    retry = session.send.retry
    retry.stop = _StopAfterTransientFailures() | retry.stop
    send = session.send

    @wraps(send)
    def send_with_status_check(request, **kwargs):
        response = send(request, **kwargs)
        # RESTClient calls send directly, bypassing Session.request's status check.
        # Raise only after the retry loop finishes so scope handlers can skip it.
        response.raise_for_status()
        return response

    session.send = send_with_status_check
    return session
