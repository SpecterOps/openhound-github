from typing import Optional

from requests import Response


def _response_message(response: Response) -> str:
    try:
        response_data = response.json()
    except ValueError:
        return getattr(response, "text", "")
    if isinstance(response_data, dict):
        return str(response_data.get("message", ""))
    return ""


def is_primary_rate_limit_response(response: Response) -> bool:
    if response.status_code not in (403, 429):
        return False

    message = _response_message(response).lower()
    return (
        response.headers.get("x-ratelimit-remaining") == "0"
        or "api rate limit exceeded" in message
    )


def is_secondary_rate_limit_response(response: Response) -> bool:
    if response.status_code not in (403, 429):
        return False

    message = _response_message(response).lower()
    return "secondary rate limit" in message or "abuse detection" in message


def should_retry_github_response(
    response: Optional[Response], exception: Optional[BaseException]
) -> bool:
    if response is None:
        return False

    return (
        is_primary_rate_limit_response(response)
        or is_secondary_rate_limit_response(response)
        or (
            response.status_code in (403, 429)
            and bool(response.headers.get("Retry-After"))
        )
    )
