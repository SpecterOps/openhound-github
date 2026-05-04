from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Optional, Union

import dlt
from dlt.common.configuration import configspec
from dlt.common.configuration.specs import CredentialsConfiguration
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import (
    HeaderLinkPaginator,
    OffsetPaginator,
)

from openhound_github.auth import create_github_jwt_session
from openhound_github.graphql import (
    MEMBERS_WITH_ROLE_QUERY,
    PROTECTION_RULES_QUERY,
    REF_OVERFLOW_QUERY,
    REPO_REFS_QUERY,
    SAML_IDENTITIES_QUERY,
    SAML_QUERY,
    TEAM_MEMBERS_OVERFLOW_QUERY,
    TEAMS_QUERY,
)
from openhound_github.helpers import GraphQLCursorPaginator
from openhound_github.main import app
from openhound_github.models import (
    ActionPermission,
    App,
    AppInstallation,
    BaseRepoRole,
    Branch,
    BranchProtectionRule,
    Environment,
    EnvironmentBranchPolicy,
    EnvironmentSecret,
    EnvironmentVariable,
    ExternalIdentity,
    Organization,
    OrgRole,
    OrgRoleMember,
    OrgRoleTeam,
    OrgRunner,
    OrgRunnerGroupMembership,
    OrgSecret,
    OrgVariable,
    PatRepoAccess,
    PersonalAccessToken,
    PersonalAccessTokenRequest,
    RepoRole,
    RepoRoleAssignment,
    RepoRunner,
    RepoSecret,
    Repository,
    RepositoryQL,
    RepoVariable,
    RunnerGroup,
    SamlProvider,
    ScimResource,
    SecretScanningAlert,
    SelectedOrgSecret,
    SelectedOrgVariable,
    Team,
    TeamMember,
    TeamRole,
    User,
    Workflow,
)
from openhound_github.models.repo_role_assignment import TEAM_PERMISSION_MAP
from openhound_github.models.repository_role import DEFAULT_REPO_ROLES

from .resources.enterprise import enterprise_resources
from .resources.organization import organization_resources


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    org_name: str | None = None
    enterprise_name: str | None = None


def _runner_group_repo_node_ids(
    group: dict[str, Any], ctx: SourceContext, repos: list
) -> list[str]:
    visibility = group.get("visibility")
    if visibility == "selected":
        repo_node_ids: list[str] = []
        try:
            for page in ctx.client.paginate(
                f"/orgs/{ctx.org_name}/actions/runner-groups/{group['id']}/repositories",
                params={"per_page": 100},
                data_selector="repositories",
            ):
                repo_node_ids.extend(
                    repo.get("node_id") for repo in page if repo.get("node_id")
                )
        except Exception:
            return []
        return repo_node_ids

    repo_node_ids = []
    for repo in repos:
        repo_node_id = (
            repo.node_id if isinstance(repo, Repository) else repo.get("node_id")
        )
        repo_visibility = (
            repo.visibility if isinstance(repo, Repository) else repo.get("visibility")
        )
        if visibility == "all":
            repo_node_ids.append(repo_node_id)
        elif visibility == "private" and repo_visibility in {
            "private",
            "internal",
        }:
            repo_node_ids.append(repo_node_id)
    return [node_id for node_id in repo_node_ids if node_id]


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
        org_name=credentials.org_name,
        enterprise_name=credentials.enterprise_name,
    )

    if credentials.org_name:
        return organization_resources(ctx)
