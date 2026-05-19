import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional, Union

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


def _has_graphql_errors(response: requests.Response) -> bool:
    try:
        response_data = response.json()
    except ValueError:
        return False
    return isinstance(response_data, dict) and bool(response_data.get("errors"))


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
    cache_lock: Lock = field(default_factory=Lock)
    app_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    actions_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    runner_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    workflow_permissions_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

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


def github_retry_policy(auth: GitHubAppInstallationAuth):
    def retry_policy(
        response: Optional[requests.Response], exception: Optional[BaseException]
    ) -> bool:
        if response is None:
            return False

        headers = response.headers
        now = int(time.time())
        if (
            response.status_code == 200
            and headers.get("x-ratelimit-resource") == "graphql"
            and _has_graphql_errors(response)
        ):
            if headers.get("Retry-After"):
                return True

            if headers.get("x-ratelimit-remaining") == "0":
                reset_at = headers.get("x-ratelimit-reset")
                delay = int(reset_at) - now if reset_at else 0
                headers["Retry-After"] = str(delay)
                logger.warning(
                    "Primary rate limit reached, retrying in %s seconds", delay
                )
                return True
            return False

        message = _response_message(response).lower()
        if response.status_code not in (403, 429):
            return False

        if (
            headers.get("x-ratelimit-remaining") == "0"
            or "api rate limit exceeded" in message
        ):
            reset_at = headers.get("x-ratelimit-reset")
            delay = int(reset_at) - now if reset_at else 0
            headers["Retry-After"] = str(delay)
            logger.warning("Primary rate limit reached, retrying in %s seconds", delay)
            return True

        if "secondary rate limit" in message or "abuse detection" in message:
            logger.warning("Secondary rate limit reached, retrying in 60 seconds")
            headers["Retry-After"] = "60"
            return True

        if headers.get("Retry-After"):
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

    def client(auth: GitHubAppInstallationAuth) -> RESTClient:
        return RESTClient(
            base_url=host,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=auth,
            paginator=HeaderLinkPaginator(),
            session=requests.Client(
                status_codes=tuple(range(500, 600)),
                retry_condition=github_retry_policy(auth),
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
        ctx.organizations.append(
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
