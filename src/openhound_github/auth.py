"""GitHub authentication helpers for JWT-based app authentication."""

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Iterator

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from dlt.common.configuration import configspec
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    HeaderLinkPaginator,
)
from joserfc import jwk, jwt
from joserfc.jwk import RSAKey


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
        org_name: str,
        installation_id: str,
        client_id: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.installation_id = installation_id
        self.org_name = org_name
        super().__init__(client_id, private_key_path, api_uri)

    @property
    def token(self) -> dict:
        response = self.client.post(
            f"{self.api_uri}app/installations/{self.installation_id}/access_tokens",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


class GithubApp(GithubSession):
    def __init__(
        self,
        enterprise_name: str,
        client_id: str,
        private_key_path: str,
        api_uri: str = "https://api.github.com/",
    ):
        self.enterprise_name = enterprise_name
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.api_uri = api_uri
        super().__init__(client_id, private_key_path, api_uri)

    @property
    def installations(self) -> Iterator[dict]:
        for page in self.client.paginate(
            "/app/installations", params={"per_page": 100}
        ):
            yield from page

    def install_id_for_org(self, org_login: str) -> int:
        response = self.client.get(f"/orgs/{org_login}/installation")
        response.raise_for_status()
        return int(response.json()["id"])


class GitHubJwtSession:
    """Manages GitHub JWT-based authentication for GitHub Apps."""

    def __init__(
        self,
        client_id: str,
        private_key_path: str,
        app_id: str | None = None,
        org_name: str | None = None,
        api_uri: str = "https://api.github.com/",
    ):
        """Initialize a GitHub JWT session.

        Args:
            org_name: The GitHub organization name.
            client_id: The GitHub App client ID.
            private_key_path: Path to the private key PEM file.
            app_id: The GitHub App ID.
            api_uri: The GitHub API base URI (default: https://api.github.com/).

        Raises:
            FileNotFoundError: If the private key file cannot be found.
            ValueError: If the private key cannot be loaded or JWT cannot be created.
        """
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.app_id = app_id
        self.org_name = org_name
        self.api_uri = api_uri.rstrip("/") + "/"

        self._load_private_key()

    def _load_private_key(self) -> None:
        """Load the RSA private key from the PEM file."""
        try:
            with open(self.private_key_path, "rb") as key_file:
                key_data = key_file.read()
                self._private_key = serialization.load_pem_private_key(
                    key_data, password=None
                )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Private key file not found at {self.private_key_path}"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}") from e

    def _create_jwt(self) -> str:
        """Create a signed JWT token for GitHub App authentication.

        Returns:
            The JWT token as a string.

        Raises:
            ValueError: If JWT creation fails.
        """
        # Create header
        header = {"alg": "RS256", "typ": "JWT"}
        header_encoded = self._base64url_encode(json.dumps(header))

        # Create payload with 10-minute expiration
        now_utc = datetime.now(timezone.utc).timestamp()
        payload = {
            "iat": int(now_utc - 10),  # Issued 10 seconds in the past
            "exp": int(now_utc + 600),  # Expires in 10 minutes
            "iss": self.client_id,
        }
        payload_encoded = self._base64url_encode(json.dumps(payload))

        # Sign the JWT
        message = f"{header_encoded}.{payload_encoded}".encode("utf-8")
        try:
            signature = self._private_key.sign(
                message, padding.PKCS1v15(), hashes.SHA256()
            )
            signature_encoded = self._base64url_encode(signature)
        except Exception as e:
            raise ValueError(f"Failed to sign JWT: {e}") from e

        return f"{header_encoded}.{payload_encoded}.{signature_encoded}"

    @staticmethod
    def _base64url_encode(data: str | bytes) -> str:
        """Encode data using base64url encoding (without padding).

        Args:
            data: The data to encode (string or bytes).

        Returns:
            Base64url encoded string without padding.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        elif isinstance(data, bytes):
            pass
        else:
            raise TypeError("Data must be string or bytes")

        encoded = base64.urlsafe_b64encode(data).decode("utf-8")
        # Remove padding
        return encoded.rstrip("=")

    @property
    def jwt_headers(self) -> dict:
        jwt_token = self._create_jwt()
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def jwt_token(self) -> str:
        return self._create_jwt()

    def _jwt_client(self) -> RESTClient:
        return RESTClient(
            base_url=self.api_uri,
            headers=self.jwt_headers,
        )

    def list_installations(self) -> Iterator[dict]:
        for page in self._jwt_client().paginate(
            "/app/installations", params={"per_page": 100}
        ):
            yield from page

    def installation_id_for_org(self, org_login: str) -> int:
        response = self._jwt_client().get(f"/orgs/{org_login}/installation").json()
        return int(response["id"])

    def create_installation_token(
        self, installation_id: int
    ) -> tuple[str, datetime | None]:
        try:
            response = requests.post(
                f"{self.api_uri}app/installations/{installation_id}/access_tokens",
                headers=self.jwt_headers,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(
                f"Failed to obtain access token from GitHub API: {e}"
            ) from e

        response_data = response.json()
        if "token" not in response_data:
            raise ValueError("No token in GitHub API response. Check app credentials.")

        expires_at = None
        if "expires_at" in response_data:
            expires_at = datetime.fromisoformat(
                response_data["expires_at"].replace("Z", "+00:00")
            )

        token = response_data["token"]
        return token, expires_at

    def get_access_token(
        self, org_name: str | None = None, installation_id: int | None = None
    ) -> str:
        """Get a valid access token for GitHub API requests.

        Fetches a new installation access token using a freshly signed JWT.
        Request-time token caching is handled by GitHubAppInstallationAuth.

        Returns:
            A valid access token string.

        Raises:
            requests.RequestException: If the API request fails.
            ValueError: If token cannot be obtained.
        """
        if installation_id is None:
            org_login = org_name or self.org_name
            if org_login:
                installation_id = self.installation_id_for_org(org_login)
            else:
                if not self.app_id:
                    raise ValueError("org_name or installation_id is required")
                installation_id = int(self.app_id)

        token, _ = self.create_installation_token(installation_id)
        return token

    def get_headers(self) -> dict:
        """Get HTTP headers for authenticated GitHub API requests.

        Returns:
            A dictionary of headers including the Authorization bearer token.
        """
        token = self.get_access_token()
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }


@configspec
class GitHubAppInstallationAuth(AuthConfigBase):
    """Requests auth that refreshes GitHub App installation tokens as needed."""

    def __init__(
        self,
        session: GitHubJwtSession,
        installation_id: int,
        refresh_margin_seconds: int = 300,
    ):
        self.session = session
        self.installation_id = installation_id
        self.refresh_margin_seconds = refresh_margin_seconds
        self.access_token: str | None = None
        self.expires_at: datetime | None = None

    def _should_refresh(self) -> bool:
        if self.access_token is None:
            return True
        if self.expires_at is None:
            return False
        refresh_at = self.expires_at - timedelta(seconds=self.refresh_margin_seconds)
        return datetime.now(timezone.utc) >= refresh_at

    def token(self, *, force_refresh: bool = False) -> str:
        if force_refresh or self._should_refresh():
            self.access_token, self.expires_at = self.session.create_installation_token(
                self.installation_id
            )
        if self.access_token is None:
            raise ValueError("GitHub App installation token was not initialized")
        return self.access_token

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        return request

    def refresh_prepared_request(
        self, request: requests.PreparedRequest | None
    ) -> bool:
        if request is None:
            return False
        current_authorization = request.headers.get("Authorization")
        if (
            current_authorization
            == getattr(request, "_openhound_refreshed_authorization", None)
            and not self._should_refresh()
        ):
            return False
        token = self.token(force_refresh=True)
        refreshed_authorization = f"Bearer {token}"
        request.headers["Authorization"] = refreshed_authorization
        setattr(request, "_openhound_refreshed_authorization", refreshed_authorization)
        return True

    def should_retry_unauthorized(self, response: requests.Response) -> bool:
        if response.status_code != 401:
            return False
        try:
            response_data = response.json()
        except ValueError:
            message = getattr(response, "text", "")
        else:
            message = (
                response_data.get("message", "")
                if isinstance(response_data, dict)
                else ""
            )
        if "bad credentials" not in message.lower():
            return False
        return self.refresh_prepared_request(getattr(response, "request", None))


def create_github_jwt_session(
    org_name: str | None,
    client_id: str,
    private_key_path: str,
    app_id: str,
    api_uri: str = "https://api.github.com",
) -> GitHubJwtSession:
    """Factory function to create a GitHub JWT session.

    Args:
        org_name: The GitHub organization name.
        client_id: The GitHub App client ID.
        private_key_path: Path to the private key PEM file.
        app_id: The GitHub App ID.

    Returns:
        A GitHubJwtSession instance.

    Example:
        >>> session = create_github_jwt_session(
        ...     org_name="my-org",
        ...     client_id="Iv1.abc123...",
        ...     private_key_path="/path/to/private-key.pem",
        ...     app_id="123456"
        ... )
        >>> token = session.get_access_token()
        >>> headers = session.get_headers()
    """
    return GitHubJwtSession(
        org_name=org_name,
        client_id=client_id,
        private_key_path=private_key_path,
        app_id=app_id,
        api_uri=api_uri,
    )
