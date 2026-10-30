import json
from unittest.mock import Mock

import pytest
from dlt.sources.helpers import requests as dlt_requests
from requests import HTTPError, Response
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth

from openhound_github.github_rest_client import github_http_session, should_retry_github_response
from openhound_github.helpers import github_retry_policy


def make_response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
    text: str | None = None,
) -> Response:
    response = Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    if body is not None:
        response._content = json.dumps(body).encode("utf-8")
        response.headers.setdefault("Content-Type", "application/json")
    else:
        response._content = (text or "").encode("utf-8")
    response.url = "https://api.github.com/example"
    return response


def test_retries_primary_rate_limit_response() -> None:
    response = make_response(
        403,
        headers={"x-ratelimit-remaining": "0"},
        body={"message": "API rate limit exceeded"},
    )

    assert should_retry_github_response(response, None) is True


def test_retries_secondary_rate_limit_response() -> None:
    response = make_response(
        429,
        body={"message": "You have exceeded a secondary rate limit."},
    )

    assert should_retry_github_response(response, None) is True


def test_does_not_retry_non_rate_limit_403() -> None:
    response = make_response(
        403,
        body={"message": "Resource not accessible by integration"},
    )

    assert should_retry_github_response(response, None) is False


def _session(monkeypatch, outcomes):
    session = github_http_session(github_retry_policy(BearerTokenAuth("test")))
    send = Mock(side_effect=outcomes)
    monkeypatch.setattr(session.get_adapter("https://"), "send", send)
    session.send.retry.sleep = lambda _: None
    return session, send


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_failures_stop_after_three_attempts(monkeypatch, status):
    session, send = _session(monkeypatch, [make_response(status) for _ in range(4)])

    with pytest.raises(HTTPError) as caught:
        session.get("https://api.github.com/example")

    assert caught.value.response.status_code == status
    assert send.call_count == 3
    assert all(call.kwargs["timeout"] == (10, 30) for call in send.call_args_list)


@pytest.mark.parametrize("error", [ReadTimeout, ConnectionError, ChunkedEncodingError])
def test_network_failures_stop_after_three_attempts(monkeypatch, error):
    session, send = _session(monkeypatch, [error("interrupted") for _ in range(4)])

    with pytest.raises(error):
        session.get("https://api.github.com/example")

    assert send.call_count == 3


def test_transient_failure_count_resets_for_each_request(monkeypatch):
    session, send = _session(monkeypatch, [
        make_response(503), make_response(503), make_response(200),
        make_response(503), make_response(503), make_response(200),
    ])

    assert session.get("https://api.github.com/example").status_code == 200
    assert session.get("https://api.github.com/example").status_code == 200
    assert send.call_count == 6


def test_mixed_server_and_network_failures_share_budget(monkeypatch):
    session, send = _session(monkeypatch, [
        make_response(503), ReadTimeout("interrupted"), make_response(502),
        make_response(200),
    ])

    with pytest.raises(HTTPError):
        session.get("https://api.github.com/example")

    assert send.call_count == 3


def test_rate_limit_retries_do_not_consume_transient_budget(monkeypatch):
    session, send = _session(monkeypatch, [
        *[make_response(429, body={"message": "secondary rate limit"}) for _ in range(4)],
        make_response(503), make_response(503), make_response(200),
    ])

    assert session.get("https://api.github.com/example").status_code == 200
    assert send.call_count == 7


@pytest.mark.parametrize(("status", "headers", "body"), [
    (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "4102444800"},
     {"message": "API rate limit exceeded"}),
    (429, {}, {"message": "secondary rate limit"}),
    (429, {"Retry-After": "12"}, {"message": "Please wait"}),
    (200, {"x-ratelimit-resource": "graphql", "x-ratelimit-remaining": "0",
           "x-ratelimit-reset": "4102444800"},
     {"errors": [{"message": "API rate limit exceeded"}]}),
])
def test_rate_limit_attempts_and_waits_match_existing_session(
    monkeypatch, status, headers, body,
):
    monkeypatch.setenv("RUNTIME__REQUEST_MAX_ATTEMPTS", "5")
    observations = []
    for updated in (False, True):
        policy = github_retry_policy(BearerTokenAuth("test"))
        session = (
            github_http_session(policy) if updated else dlt_requests.Client(
                status_codes=tuple(range(500, 600)), retry_condition=policy,
            ).session
        )
        send = Mock(side_effect=[
            make_response(status, headers=headers, body=body) for _ in range(5)
        ])
        monkeypatch.setattr(session.get_adapter("https://"), "send", send)
        sleep = Mock()
        session.send.retry.sleep = sleep
        if status != 200:
            with pytest.raises(HTTPError):
                session.get("https://api.github.com/example")
        else:
            response = session.get("https://api.github.com/graphql")
            assert response.json()["errors"]
        observations.append((send.call_count, [float(c.args[0]) for c in sleep.call_args_list]))

    assert observations[0][0] == 5
    assert len(observations[0][1]) == 4
    assert observations[1] == observations[0]
