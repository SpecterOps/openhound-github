import json

from requests import Response

from openhound_github.github_rest_client import should_retry_github_response


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
