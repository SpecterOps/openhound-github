import json

from requests import Response

from openhound_github.github_retry import (
    is_primary_rate_limit_response,
    is_secondary_rate_limit_response,
    should_retry_github_response,
)


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


def test_primary_rate_limit_is_retryable() -> None:
    response = make_response(
        403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000030",
        },
        body={"message": "API rate limit exceeded"},
    )

    assert is_primary_rate_limit_response(response) is True
    assert should_retry_github_response(response, None) is True


def test_secondary_rate_limit_is_retryable() -> None:
    response = make_response(
        429,
        headers={"Retry-After": "17"},
        body={"message": "You have exceeded a secondary rate limit."},
    )

    assert is_secondary_rate_limit_response(response) is True
    assert should_retry_github_response(response, None) is True


def test_secondary_rate_limit_uses_response_message() -> None:
    response = make_response(
        403,
        body={"message": "You have exceeded a secondary rate limit."},
    )

    assert is_secondary_rate_limit_response(response) is True
    assert should_retry_github_response(response, None) is True


def test_non_rate_limit_403_is_not_marked_retryable() -> None:
    response = make_response(
        403,
        body={"message": "Resource not accessible by integration"},
    )

    assert is_primary_rate_limit_response(response) is False
    assert is_secondary_rate_limit_response(response) is False
    assert should_retry_github_response(response, None) is False
