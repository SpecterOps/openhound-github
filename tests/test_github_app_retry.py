from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock

import requests
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth

from openhound_github.auth import GitHubAppInstallationAuth, TokenResponse
from openhound_github.helpers import github_retry_policy


class FakeInstallation:
    installation_id = "12345"

    def __init__(self, *tokens: str) -> None:
        self._tokens = iter(tokens)
        self.token_calls = 0

    @property
    def token(self) -> TokenResponse:
        self.token_calls += 1
        return TokenResponse(
            token=next(self._tokens),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )


class BlockingFakeInstallation(FakeInstallation):
    def __init__(self, *tokens: str) -> None:
        super().__init__(*tokens)
        self.token_started = Event()
        self.release_token = Event()

    @property
    def token(self) -> TokenResponse:
        self.token_started.set()
        if not self.release_token.wait(timeout=1):
            raise TimeoutError("timed out waiting to release fake token refresh")
        return super().token


class TrackingLock:
    def __init__(self) -> None:
        self._lock = Lock()
        self.waiting = Event()

    def __enter__(self):
        if not self._lock.acquire(blocking=False):
            self.waiting.set()
            self._lock.acquire()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self._lock.release()


def prepared_request(token: str) -> requests.PreparedRequest:
    return requests.Request(
        "GET",
        "https://api.github.com/repos/example/repo",
        headers={"Authorization": f"Bearer {token}"},
    ).prepare()


def bad_credentials_response(
    request: requests.PreparedRequest,
) -> requests.Response:
    response = requests.Response()
    response.status_code = 401
    response._content = b'{"message":"Bad credentials"}'
    response.request = request
    return response


def test_refresh_request_refreshes_rejected_current_token() -> None:
    installation = FakeInstallation("new-token")
    auth = GitHubAppInstallationAuth(installation=installation)
    auth.access_token = "old-token"
    auth.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    request = prepared_request("old-token")

    auth.refresh_request(request)

    assert request.headers["Authorization"] == "Bearer new-token"
    assert auth.access_token == "new-token"
    assert installation.token_calls == 1


def test_refresh_request_reuses_token_refreshed_by_another_request() -> None:
    installation = BlockingFakeInstallation("new-token")
    auth = GitHubAppInstallationAuth(installation=installation)
    auth.access_token = "old-token"
    auth.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    auth._token_lock = TrackingLock()
    requests_to_refresh = [prepared_request("old-token"), prepared_request("old-token")]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_refresh = executor.submit(auth.refresh_request, requests_to_refresh[0])
        assert installation.token_started.wait(timeout=1)

        second_refresh = executor.submit(auth.refresh_request, requests_to_refresh[1])
        assert auth._token_lock.waiting.wait(timeout=1)

        installation.release_token.set()
        first_refresh.result(timeout=1)
        second_refresh.result(timeout=1)

    assert all(
        request.headers["Authorization"] == "Bearer new-token"
        for request in requests_to_refresh
    )
    assert installation.token_calls == 1


def test_retry_policy_repairs_bad_credentials_for_github_app_auth() -> None:
    installation = FakeInstallation("new-token")
    auth = GitHubAppInstallationAuth(installation=installation)
    auth.access_token = "old-token"
    auth.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    request = prepared_request("old-token")

    should_retry = github_retry_policy(auth)(bad_credentials_response(request), None)

    assert should_retry is True
    assert request.headers["Authorization"] == "Bearer new-token"
    assert installation.token_calls == 1


def test_retry_policy_does_not_repair_bad_credentials_for_bearer_token_auth() -> None:
    request = prepared_request("static-token")

    should_retry = github_retry_policy(BearerTokenAuth(token="static-token"))(
        bad_credentials_response(request),
        None,
    )

    assert should_retry is False
    assert request.headers["Authorization"] == "Bearer static-token"
