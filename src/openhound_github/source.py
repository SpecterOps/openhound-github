import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Union

import dlt
from dlt.common.configuration import configspec
from dlt.common.configuration.specs import CredentialsConfiguration
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
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
from openhound_github.helpers import github_retry_policy
from openhound_github.main import app
from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    github_deployment_context,
)

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources

logger = logging.getLogger(__name__)


@dataclass
class OrgContext:
    client: RESTClient
    org_name: str
    enterprise_name: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN


@dataclass
class SourceContext:
    organizations: list[OrgContext] | None = field(default_factory=list)
    client: RESTClient | None = None
    sso_client: RESTClient | None = None
    enterprise_name: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN
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
    pat_token: str | None = None
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
    github_deployment_id, github_web_origin = github_deployment_context(host)

    def client(auth: AuthConfigBase) -> RESTClient:
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
        ctx = SourceContext(
            enterprise_name=credentials.enterprise_name,
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
        if credentials.pat_token:
            ctx.sso_client = client(BearerTokenAuth(token=credentials.pat_token))
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
                        github_deployment_id=github_deployment_id,
                        github_web_origin=github_web_origin,
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
        ctx = SourceContext(
            enterprise_name=None,
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
        org_installation = GithubInstallation(
            installation_id=credentials.install_id,
            client_id=credentials.client_id,
            private_key_path=credentials.key_path,
        )
        ctx.organizations.append(
            OrgContext(
                org_name=credentials.org_name,
                client=client(GitHubAppInstallationAuth(installation=org_installation)),
                github_deployment_id=github_deployment_id,
                github_web_origin=github_web_origin,
            )
        )

        return organization_resources(ctx)

    else:
        ctx = SourceContext(
            github_deployment_id=github_deployment_id,
            github_web_origin=github_web_origin,
        )
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
                github_deployment_id=github_deployment_id,
                github_web_origin=github_web_origin,
            )
        )
        return organization_resources(ctx)
