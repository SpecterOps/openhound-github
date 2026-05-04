from dataclasses import dataclass
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

from openhound_github.auth import create_github_jwt_session
from openhound_github.main import app

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    org_names: list[str] | None = None
    enterprise_name: str | None = None


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

    def auth(self) -> str:
        return "app"

    @property
    def header(self) -> str:
        github_access_token = create_github_jwt_session(
            org_name=self.org_name,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
        ).get_access_token()
        return github_access_token


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

    if credentials.org_name:
        ctx.org_names = [credentials.org_name]
        return organization_resources(ctx)

    elif credentials.enterprise_name:
        ctx.enterprise_name = credentials.enterprise_name
        return enterprise_resources(ctx)

    else:
        raise ValueError("Must specify either enterprise_name or org_name")
