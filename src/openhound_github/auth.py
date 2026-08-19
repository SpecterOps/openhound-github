import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Iterator
from urllib.parse import urlparse

import requests
from dlt.common.configuration import configspec
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    HeaderLinkPaginator,
)
from joserfc import jwt
from joserfc.jwk import RSAKey
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _normalized_http_origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("GitHub API URI must be an absolute HTTP(S) URL")

    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    return scheme, parsed.hostname.lower(), port


class AccountConfig(BaseModel):
    id: int
    login: str | None = None
    name: str | None = None
    type: str | None = None
    slug: str | None = None


class InstallationResponse(BaseModel):
    id: int
    client_id: str | None = None
    account: AccountConfig
    target_type: str
    app_id: int | None = None
    app_slug: str | None = None


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime


def resolve_github_app_jwt_issuer(
    *, client_id: str | None, app_id: str | int | None
) -> str:
    """Select the configured identifier for GitHub App JWT authentication."""
    normalized_client_id = str(client_id).strip() if client_id is not None else ""
    if normalized_client_id:
        return normalized_client_id

    normalized_app_id = str(app_id).strip() if app_id is not None else ""
    if normalized_app_id:
        return normalized_app_id

    raise ValueError(
        "GitHub App credentials require either client_id or app_id for the JWT issuer"
    )


class GithubSession:
    def __init__(
        self,
        jwt_issuer: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        _normalized_http_origin(api_uri)
        self.api_uri = f"{api_uri.rstrip('/')}/"
        self.jwt_issuer = jwt_issuer
        self.private_key_path = private_key_path
        self.client = RESTClient(
            base_url=self.api_uri,
            paginator=HeaderLinkPaginator(),
        )

    @property
    def jwt(self) -> str:
        now_utc = datetime.now(timezone.utc).timestamp()
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": self.jwt_issuer,
            "iat": int(now_utc - 10),  # Issued 10 seconds in the past
            "exp": int(
                now_utc + 540
            ),  # Expires in 9 minutes (GitHub max is 10, leaving room for clock drift)
        }

        try:
            with open(self.private_key_path, "rb") as key_file:
                key = RSAKey.import_key(key_file.read())
                text = jwt.encode(header, claims, key)
                return text

        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}") from e

    @property
    def jwt_headers(self) -> dict:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.jwt}",
            "X-GitHub-Api-Version": "2022-11-28",
        }


class GithubInstallation(GithubSession):
    def __init__(
        self,
        installation_id: str,
        jwt_issuer: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.installation_id = installation_id
        super().__init__(jwt_issuer, private_key_path, api_uri)

    @property
    def token(self) -> TokenResponse:
        logger.info(f"Getting access token for {self.installation_id}")
        response = self.client.post(
            f"{self.api_uri}app/installations/{self.installation_id}/access_tokens",
            timeout=10,
            headers=self.jwt_headers,
        )
        response.raise_for_status()
        return TokenResponse(**response.json())


class GithubApp(GithubSession):
    def __init__(
        self,
        jwt_issuer: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        super().__init__(jwt_issuer, private_key_path, api_uri)

    @property
    def installations(self) -> Iterator[InstallationResponse]:
        for page in self.client.paginate(
            "/app/installations", params={"per_page": 100}, headers=self.jwt_headers
        ):
            for item in page:
                yield InstallationResponse(**item)

    def install_id_for_org(self, org_login: str) -> int:
        logger.info(f"Getting app installation ID for org {org_login}")
        response = self.client.get(
            f"/orgs/{org_login}/installation", headers=self.jwt_headers
        )
        response.raise_for_status()
        return int(response.json()["id"])


@configspec
class GitHubAppInstallationAuth(AuthConfigBase):
    """Requests auth that refreshes GitHub App installation tokens as needed."""

    def __init__(
        self,
        installation: GithubInstallation,
        refresh_margin_seconds: int = 300,
        api_uri: str | None = None,
    ):
        self.installation = installation
        self.refresh_margin_seconds = refresh_margin_seconds
        self.api_uri = api_uri or getattr(
            installation, "api_uri", "https://api.github.com/"
        )
        self._api_origin = _normalized_http_origin(self.api_uri)
        self.access_token: str | None = None
        self.expires_at: datetime | None = None
        self._response_refreshed_token: str | None = None
        self._token_lock = Lock()

    def _should_refresh(self) -> bool:
        if self.expires_at is None:
            return True

        refresh_at = self.expires_at - timedelta(seconds=self.refresh_margin_seconds)
        return datetime.now(timezone.utc) >= refresh_at

    def _refresh_token(self, *, response_triggered: bool = False) -> None:
        logger.info(
            f"Refreshing access token for {self.installation.installation_id}"
        )
        get_token = self.installation.token
        self.access_token = get_token.token
        self.expires_at = get_token.expires_at
        self._response_refreshed_token = (
            get_token.token if response_triggered else None
        )

    def token(self, force_refresh: bool = False) -> str | None:
        if (
            not force_refresh
            and self.access_token is not None
            and not self._should_refresh()
        ):
            return self.access_token

        with self._token_lock:
            if (force_refresh or self._should_refresh()) or self.access_token is None:
                self._refresh_token()

        return self.access_token

    def refresh_request(self, request: requests.PreparedRequest) -> bool:
        """Repair a rejected same-origin request without stampeding token issuance."""
        try:
            request_origin = _normalized_http_origin(request.url or "")
        except ValueError:
            return False

        if request_origin != self._api_origin:
            return False

        request_authorization = request.headers.get("Authorization")
        if (
            not request_authorization
            or not request_authorization.startswith("Bearer ")
            or not request_authorization.removeprefix("Bearer ").strip()
        ):
            return False

        with self._token_lock:
            current_authorization = (
                f"Bearer {self.access_token}" if self.access_token is not None else None
            )
            should_refresh = self._should_refresh()
            if (
                not should_refresh
                and request_authorization == current_authorization
                and self.access_token == self._response_refreshed_token
            ):
                return False

            if (
                self.access_token is None
                or should_refresh
                or request_authorization == current_authorization
            ):
                try:
                    self._refresh_token(response_triggered=True)
                except Exception:
                    logger.warning(
                        "Failed to refresh GitHub App installation token for "
                        "installation %s during request retry",
                        self.installation.installation_id,
                    )
                    return False

            request.headers["Authorization"] = f"Bearer {self.access_token}"

        return True

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        return request

    #
