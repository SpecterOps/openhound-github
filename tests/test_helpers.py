import json
from types import SimpleNamespace

import pytest
import requests
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.requests.retry import Client
from dlt.sources.helpers.requests.session import Session

from openhound_github.helpers import _rest_api_url, github_retry_policy


@pytest.mark.parametrize(
    "base_url, expected",
    [
        (None, "https://api.github.com"),
        ("", "https://api.github.com"),
        (" \t ", "https://api.github.com"),
        ("https://api.example.ghe.com/", "https://api.example.ghe.com"),
        ("  https://github.example/api/v3/  ", "https://github.example/api/v3"),
    ],
)
def test_rest_api_url_normalizes_optional_client_base(base_url, expected):
    """Normalize absent or blank bases and preserve custom API hosts and paths."""
    assert _rest_api_url(SimpleNamespace(base_url=base_url)) == expected


def test_rest_api_url_defaults_when_base_attribute_is_missing():
    """Use GitHub's default API URL when a client supplies no base attribute."""
    assert _rest_api_url(SimpleNamespace()) == "https://api.github.com"


def graphql_response(
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
    text: str | None = None,
    url: str = "https://ghe.example/api/v3/graphql",
) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.headers.update(headers or {})
    if text is not None:
        response._content = text.encode("utf-8")
    else:
        response._content = json.dumps(body or {}).encode("utf-8")
    response.request = requests.Request("POST", url).prepare()
    return response


def test_retry_policy_recognizes_graphql_endpoint_without_resource_header() -> None:
    response = graphql_response(
        headers={"Retry-After": "0"},
        body={"errors": [{"message": "temporary GraphQL failure"}]},
    )

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        response,
        None,
    )

    assert should_retry is True


def test_retry_policy_retries_malformed_graphql_json() -> None:
    response = graphql_response(text='{"data":{"organization":')

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        response,
        None,
    )

    assert should_retry is True


def test_retry_policy_does_not_retry_malformed_non_graphql_json() -> None:
    response = graphql_response(
        text='{"data":{"organization":',
        url="https://ghe.example/api/v3/repos/example/repo",
    )

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        response,
        None,
    )

    assert should_retry is False


def test_retry_client_recovers_from_malformed_graphql_json(monkeypatch) -> None:
    responses = [
        graphql_response(text='{"data":{"organization":'),
        graphql_response(body={"data": {"organization": {"repositories": {}}}}),
    ]
    requests_seen: list[requests.PreparedRequest] = []

    def fake_send(
        _session: Session,
        request: requests.PreparedRequest,
        **_kwargs,
    ) -> requests.Response:
        response = responses[len(requests_seen)]
        response.request = request
        requests_seen.append(request)
        return response

    monkeypatch.setattr(Session, "send", fake_send)
    session = Client(
        raise_for_status=False,
        status_codes=(),
        exceptions=(),
        request_max_attempts=2,
        request_backoff_factor=0,
        retry_condition=github_retry_policy(BearerTokenAuth(token="static-token")),
    ).session
    request = requests.Request(
        "POST",
        "https://ghe.example/api/v3/graphql",
    ).prepare()

    response = session.send(request)

    assert response.json() == {"data": {"organization": {"repositories": {}}}}
    assert len(requests_seen) == 2


def test_rate_limit_warning_logs_path_without_query(caplog) -> None:
    response = graphql_response(
        url="https://api.github.com/enterprises/example/credentials/exports?token=private",
        body={"message": "You have exceeded a secondary rate limit"},
    )
    response.status_code = 403

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        response, None
    )

    assert should_retry is False
    assert "POST /enterprises/example/credentials/exports" in caplog.text
    assert "skipping export creation retry" in caplog.text
    assert "token=private" not in caplog.text


def test_credential_export_429_is_not_retried(caplog) -> None:
    response = graphql_response(
        url="https://api.github.com/enterprises/example/credentials/exports",
        body={"message": "Too many requests"},
        headers={"Retry-After": "60"},
    )
    response.status_code = 429

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        response, None
    )

    assert should_retry is False
    assert "POST /enterprises/example/credentials/exports" in caplog.text
