"""GitHub authentication helpers for JWT-based app authentication."""

import json
import base64
import requests
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Optional


class GitHubJwtSession:
    """Manages GitHub JWT-based authentication for GitHub Apps."""

    def __init__(
        self,
        org_name: str,
        client_id: str,
        private_key_path: str,
        app_id: str,
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
        self.org_name = org_name
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.app_id = app_id
        self.api_uri = api_uri.rstrip("/") + "/"

        self._jwt_token: Optional[str] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: datetime | None = None

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

        jwt_token = f"{header_encoded}.{payload_encoded}.{signature_encoded}"
        self._jwt_token = jwt_token
        return jwt_token

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

    def get_access_token(self) -> str:
        """Get a valid access token for GitHub API requests.

        Fetches an installation access token using the JWT token. If a valid
        access token is already cached and not expired, it returns that.

        Returns:
            A valid access token string.

        Raises:
            requests.RequestException: If the API request fails.
            ValueError: If token cannot be obtained.
        """
        # Return cached token if still valid
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now(timezone.utc) < self._token_expires_at
        ):
            return self._access_token

        # Create a fresh JWT
        jwt_token = self._create_jwt()

        # Exchange JWT for access token
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            response = requests.post(
                f"{self.api_uri}app/installations/{self.app_id}/access_tokens",
                headers=headers,
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

        self._access_token = response_data["token"]

        # Parse expiration time if provided
        if "expires_at" in response_data:
            self._token_expires_at = datetime.fromisoformat(
                response_data["expires_at"].replace("Z", "+00:00")
            )

        return self._access_token

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


def create_github_jwt_session(
    org_name: str, client_id: str, private_key_path: str, app_id: str
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
    )
