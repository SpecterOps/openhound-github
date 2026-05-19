import logging
from datetime import datetime, timedelta, timezone
from typing import Iterator

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


class AccountConfig(BaseModel):
    id: int
    login: str | None = None
    name: str | None = None
    type: str | None = None
    slug: str | None = None


class InstallationResponse(BaseModel):
    id: int
    client_id: str
    account: AccountConfig
    target_type: str
    app_id: int | None = None
    app_slug: str | None = None


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime


class GithubSession:
    def __init__(
        self,
        client_id: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.api_uri = api_uri
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.client = RESTClient(
            base_url=self.api_uri,
            headers=self.jwt_headers,
            paginator=HeaderLinkPaginator(),
        )

    @property
    def jwt(self) -> str:
        now_utc = datetime.now(timezone.utc).timestamp()
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": self.client_id,
            "iat": int(now_utc - 10),  # Issued 10 seconds in the past
            "exp": int(now_utc + 600),  # Expires in 10 minutes
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
        client_id: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.installation_id = installation_id
        super().__init__(client_id, private_key_path, api_uri)

    @property
    def token(self) -> TokenResponse:
        logger.info(f"Getting access token for {self.installation_id}")
        response = self.client.post(
            f"{self.api_uri}app/installations/{self.installation_id}/access_tokens",
            timeout=10,
        )
        response.raise_for_status()
        return TokenResponse(**response.json())


class GithubApp(GithubSession):
    def __init__(
        self,
        client_id: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.api_uri = api_uri
        super().__init__(client_id, private_key_path, api_uri)

    @property
    def installations(self) -> Iterator[InstallationResponse]:
        for page in self.client.paginate(
            "/app/installations", params={"per_page": 100}
        ):
            for item in page:
                yield InstallationResponse(**item)

    def install_id_for_org(self, org_login: str) -> int:
        logger.info(f"Getting app installation ID for org {org_login}")
        response = self.client.get(f"/orgs/{org_login}/installation")
        response.raise_for_status()
        return int(response.json()["id"])


@configspec
class GitHubAppInstallationAuth(AuthConfigBase):
    """Requests auth that refreshes GitHub App installation tokens as needed."""

    def __init__(
        self,
        installation: GithubInstallation,
        refresh_margin_seconds: int = 300,
    ):
        self.installation = installation
        self.refresh_margin_seconds = refresh_margin_seconds
        self.access_token: str | None = None
        self.expires_at: datetime | None = None

    def _should_refresh(self) -> bool:
        if self.expires_at is None:
            return True

        refresh_at = self.expires_at - timedelta(seconds=self.refresh_margin_seconds)
        return datetime.now(timezone.utc) >= refresh_at

    def token(self, force_refresh: bool = False) -> str | None:
        if (force_refresh or self._should_refresh()) or self.access_token is None:
            logger.info(
                f"Refreshing access token for {self.installation.installation_id}"
            )
            get_token = self.installation.token
            self.access_token = get_token.token
            self.expires_at = get_token.expires_at

        return self.access_token

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        return request

    #
