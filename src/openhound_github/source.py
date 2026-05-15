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

from openhound_github.auth import create_github_jwt_session
from openhound_github.main import app

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources


@dataclass
class OrgContext:
    client: RESTClient
    org_name: str
    enterprise_name: str | None = None


@dataclass
class SourceContext:
    client: RESTClient
    organizations: list[OrgContext] | None = field(default_factory=list)
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
class GithubAppCredentials(GithubCredentials):
    client_id: str = None
    app_id: str = None
    key_path: str = None
    api_uri: str = "https://api.github.com"

    def auth(self) -> str:
        return "app"

    @property
    def header(self) -> str:
        github_app_session = create_github_jwt_session(
            org_name=self.org_name,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
            api_uri=self.api_uri,
        )
        return github_app_session.get_access_token()


@configspec
class GithubTokenCredentials(GithubCredentials):
    token: str = None

    def auth(self) -> str:
        return "token"

    @property
    def header(self) -> str:
        return f"{self.token}"


@app.source(name="github", max_table_nesting=0)
def source(
    credentials: Union[
        GithubAppCredentials, GithubTokenCredentials
    ] = dlt.secrets.value,
    host: str = "https://api.github.com",
):
    """DLT source, defines GitHub collection resources and transformers.

    Args:
        credentials (Union[GithubAppCredentials, GithubTokenCredentials]): The GitHub credentials.
        host (str): The base GitHub API URL used for API calls.
    """

    if credentials.enterprise_name and credentials.org_name:
        raise ValueError("Specify exactly one of enterprise_name and org_name")

    def retry_policy(
        response: Optional[requests.Response], exception: Optional[BaseException]
    ) -> bool:
        if response is None:
            return False

        headers = response.headers
        should_retry = (
            True
            if response.status_code in (403, 429)
            and headers.get("x-ratelimit-remaining") == "0"
            else False
        )
        return should_retry

    ctx = SourceContext(
        client=RESTClient(
            base_url=host,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=BearerTokenAuth(token=credentials.header),
            paginator=HeaderLinkPaginator(),
            session=requests.Client(retry_condition=retry_policy).session,
        ),
    )

    def org_client(token: str) -> RESTClient:
        return RESTClient(
            base_url=host,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            auth=BearerTokenAuth(token=token),
            paginator=HeaderLinkPaginator(),
            session=requests.Client(retry_condition=retry_policy).session,
        )

    # This will run when a single org_name is specified
    if credentials.org_name:
        ctx.organizations = [
            OrgContext(client=ctx.client, org_name=credentials.org_name)
        ]
        return organization_resources(ctx)

    # This will run when enterprise collection is used
    # We fetch all orgs for the enterprise and create a client for each org using the GitHub App installation token
    elif credentials.enterprise_name:
        ctx.enterprise_name = credentials.enterprise_name
        if isinstance(credentials, GithubAppCredentials):
            github_app_session = create_github_jwt_session(
                org_name=None,
                client_id=credentials.client_id,
                private_key_path=credentials.key_path,
                app_id=credentials.app_id,
                api_uri=credentials.api_uri,
            )
            ctx.organizations = [
                OrgContext(
                    client=org_client(
                        github_app_session.installation_token(installation["id"])
                    ),
                    org_name=installation["account"]["login"],
                    enterprise_name=credentials.enterprise_name,
                )
                for installation in github_app_session.list_installations()
                if installation.get("account", {}).get("type") == "Organization"
            ]
        return (*enterprise_resources(ctx), *organization_resources(ctx))

    else:
        raise ValueError("Must specify either enterprise_name or org_name")
