import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Union

import dlt
from dlt.common.configuration import configspec
from dlt.common.configuration.specs import CredentialsConfiguration
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    HeaderLinkPaginator,
)

from openhound_github.auth import (
    GithubApp,
    GitHubAppInstallationAuth,
    GithubInstallation,
)
from openhound_github.main import app

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources

logger = logging.getLogger(__name__)


def _response_message(response: requests.Response) -> str:
    try:
        response_data = response.json()
    except ValueError:
        return getattr(response, "text", "")
    if isinstance(response_data, dict):
        return response_data.get("message", "")
    return ""


@dataclass
class OrgContext:
    client: RESTClient
    org_name: str
    enterprise_name: str | None = None


@dataclass
class SourceContext:
    organizations: list[OrgContext] | None = field(default_factory=list)
    client: RESTClient | None = None
    enterprise_name: str | None = None

    @property
    def org_names(self) -> list[str]:
        return [org.org_name for org in self.organizations or []]


@configspec
class GithubCredentials(CredentialsConfiguration):
    org_name: str | None = None
    enterprise_name: str | None = None

    def auth(self):
        pass


@configspec
class GithubEnterpriseAppCredentials(CredentialsConfiguration):
    client_id: str = None
    app_id: str = None
    key_path: str = None
    enterprise_name: str = None
    api_uri: str = "https://api.github.com"

    @property
    def auth(self) -> str:
        return "enterprise_app"


@configspec
class GithubOrgAppCredentials(CredentialsConfiguration):
    client_id: str = None
    install_id: str = None
    key_path: str = None
    org_name: str = None
    api_uri: str = "https://api.github.com"

    @property
    def auth(self) -> str:
        return "org_app"


@configspec
class GithubTokenCredentials(GithubCredentials):
    token: str = None

    @property
    def auth(self) -> str:
        return "token"

    @property
    def header(self) -> str:
        return f"{self.token}"


def _retry_policy_for(auth):
    def retry_policy(
        response: Optional[requests.Response], exception: Optional[BaseException]
    ) -> bool:
        if response is None:
            return False

        headers = response.headers

        if response.status_code == 401:
            if isinstance(auth, GitHubAppInstallationAuth):
                should_retry = auth.should_retry_unauthorized(response)
                if should_retry:
                    logger.warning(
                        "GitHub App installation token rejected; refreshing and retrying"
                    )
                return should_retry
            message = _response_message(response).lower()
            if "bad credentials" in message:
                logger.warning(
                    "GitHub credentials were rejected; not retrying static token auth"
                )
            return False

        if response.status_code not in (403, 429):
            return False

        message = _response_message(response).lower()

        if headers.get("Retry-After"):
            return True

        reset_at = headers.get("x-ratelimit-reset")
        logger.warning("Rate limit reached, retrying at %s", reset_at)
        is_primary_limit = (
            headers.get("x-ratelimit-remaining") == "0"
            or "api rate limit exceeded" in message
        )
        if is_primary_limit:
            if reset_at:
                try:
                    delay = max(5, int(reset_at) - int(time.time()) + 5)
                except ValueError:
                    delay = 60
            else:
                delay = 60
            headers["Retry-After"] = str(delay)
            logger.warning("Rate limit reached, retrying in %s seconds", delay)
            return True

        if "secondary rate limit" in message or "abuse detection" in message:
            logger.warning("Secondary rate limit reached, retrying in 60 seconds")

            headers["Retry-After"] = "60"
            return True

        return False

    return retry_policy


@app.source(name="github", max_table_nesting=0)
def source(
    credentials: Union[
        GithubEnterpriseAppCredentials, GithubOrgAppCredentials, GithubTokenCredentials
    ] = dlt.secrets.value,
    host: str = "https://api.github.com",
):
    """DLT source, defines GitHub collection resources and transformers.

    Args:
        credentials (Union[GithubEnterpriseAppCredentials, GithubOrgAppCredentials, GithubTokenCredentials]): The GitHub credentials.
        host (str): The base GitHub API URL used for API calls.
    """

    def client(auth) -> RESTClient:
        return RESTClient(
            base_url=host,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=auth,
            paginator=HeaderLinkPaginator(),
            session=requests.Client(
                retry_condition=_retry_policy_for(auth),
            ).session,
        )

    if credentials.auth == "enterprise_app":
        ctx = SourceContext(enterprise_name=credentials.enterprise_name)
        github_app_session = GithubApp(
            client_id=credentials.client_id,
            private_key_path=credentials.key_path,
        )
        for installation in github_app_session.installations:
            if installation.target_type == "Organization":
                org_installation = GithubInstallation(
                    installation_id=installation.id,
                    client_id=installation.client_id,
                    private_key_path=credentials.key_path,
                )
                ctx.organizations.append(
                    OrgContext(
                        org_name=installation.account.login,
                        client=client(
                            GitHubAppInstallationAuth(installation=org_installation)
                        ),
                        enterprise_name=credentials.enterprise_name,
                    )
                )
            if installation.target_type == "Enterprise":
                es_installation = GithubInstallation(
                    installation_id=installation.id,
                    client_id=installation.client_id,
                    private_key_path=credentials.key_path,
                )
                ctx.client = client(
                    GitHubAppInstallationAuth(installation=es_installation)
                )

        return (*enterprise_resources(ctx), *organization_resources(ctx))

    elif credentials.auth == "org_app":
        ctx = SourceContext(enterprise_name=None)
        org_installation = GithubInstallation(
            installation_id=credentials.install_id,
            client_id=credentials.client_id,
            private_key_path=credentials.key_path,
        )
        ctx.organizations.append(
            OrgContext(
                org_name=credentials.org_name,
                client=client(GitHubAppInstallationAuth(installation=org_installation)),
            )
        )

        return organization_resources(ctx)

    else:
        ctx = SourceContext()
        ctx = ctx.organizations.append(
            OrgContext(
                org_name=credentials.org_name,
                client=RESTClient(
                    base_url=host,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    auth=BearerTokenAuth(token=credentials.token),
                    paginator=HeaderLinkPaginator(),
                ),
            )
        )
        return organization_resources(ctx)
