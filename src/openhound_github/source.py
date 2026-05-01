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
    ENTERPRISE_ADMINS_QUERY,
    ENTERPRISE_MEMBERS_QUERY,
    ENTERPRISE_QUERY,
    ENTERPRISE_SAML_QUERY,
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
    Enterprise,
    EnterpriseExternalIdentity,
    EnterpriseManagedUser,
    EnterpriseOrganization,
    EnterpriseRole,
    EnterpriseRoleTeam,
    EnterpriseRoleUser,
    EnterpriseSamlProvider,
    EnterpriseTeam,
    EnterpriseTeamMember,
    EnterpriseTeamOrganization,
    EnterpriseTeamRole,
    EnterpriseUser,
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
from openhound_github.models.enterprise import flatten_enterprise_member
from openhound_github.models.repo_role_assignment import TEAM_PERMISSION_MAP
from openhound_github.models.repository_role import DEFAULT_REPO_ROLES


@dataclass
class OrgContext:
    """Immutable per-organization collection context."""

    client: RESTClient
    org_name: str
    org_node_id: str | None = None


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    org_name: str | None = None
    org_node_id: str | None = None
    org_contexts: tuple[OrgContext, ...] = ()
    enterprise_name: str | None = None
    enterprise_node_id: str | None = None
    auth_type: str | None = None


def _enterprise_required(ctx: SourceContext) -> str:
    if not ctx.enterprise_name:
        raise ValueError("Enterprise resources require enterprise_name to be set.")
    return ctx.enterprise_name


def _enterprise_profile_and_orgs(
    ctx: SourceContext,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    enterprise_slug = _enterprise_required(ctx)
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.organizations.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_QUERY,
        "variables": {"slug": enterprise_slug, "after": None},
    }

    enterprise: dict[str, Any] | None = None
    organizations: list[dict[str, Any]] = []
    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        page_enterprise = page_data[0].get("enterprise")
        if not page_enterprise:
            raise ValueError(f"Enterprise '{enterprise_slug}' was not returned by GitHub.")
        if enterprise is None:
            enterprise = {k: v for k, v in page_enterprise.items() if k != "organizations"}
        for org in page_enterprise.get("organizations", {}).get("nodes", []):
            organizations.append(
                {
                    **org,
                    "enterprise_node_id": enterprise["id"],
                    "enterprise_slug": enterprise_slug,
                }
            )

    if enterprise is None:
        raise ValueError(f"Enterprise '{enterprise_slug}' was not returned by GitHub.")
    return enterprise, organizations


def _enterprise_member_records(
    ctx: SourceContext, enterprise_data: dict[str, Any]
) -> list[dict[str, Any]]:
    enterprise_slug = _enterprise_required(ctx)
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.members.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_MEMBERS_QUERY,
        "variables": {"slug": enterprise_slug, "count": 100, "after": None},
    }

    records: list[dict[str, Any]] = []
    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        enterprise_data_page = _graphql_object(page_data, "enterprise")
        for edge in _graphql_edges(enterprise_data_page.get("members")):
            node = edge.get("node")
            if node:
                records.append(
                    {
                        **node,
                        "enterprise_node_id": enterprise_data["id"],
                        "enterprise_slug": enterprise_slug,
                    }
                )
    return records


def _enterprise_saml_records(
    ctx: SourceContext,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if ctx.auth_type != "token":
        return None, []

    enterprise_slug = _enterprise_required(ctx)
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.samlIdentityProvider.externalIdentities.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_SAML_QUERY,
        "variables": {"slug": enterprise_slug, "count": 100, "after": None},
    }

    provider: dict[str, Any] | None = None
    identities: list[dict[str, Any]] = []
    try:
        for page_data in ctx.client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            enterprise_data = page_data[0].get("enterprise")
            if not enterprise_data:
                return None, []
            saml_provider = enterprise_data.get("ownerInfo", {}).get(
                "samlIdentityProvider"
            )
            if not saml_provider:
                return None, []
            if provider is None:
                provider = {
                    **{k: v for k, v in saml_provider.items() if k != "externalIdentities"},
                    "enterprise_node_id": enterprise_data["id"],
                    "enterprise_slug": enterprise_data["slug"],
                }
            for identity in _graphql_nodes(saml_provider.get("externalIdentities")):
                identities.append(
                    {
                        **identity,
                        "saml_provider_id": saml_provider["id"],
                        "saml_provider_issuer": saml_provider.get("issuer"),
                        "saml_provider_sso_url": saml_provider.get("ssoUrl"),
                        "enterprise_node_id": enterprise_data["id"],
                        "enterprise_slug": enterprise_data["slug"],
                    }
                )
    except Exception:
        return None, []

    return provider, identities


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
        if visibility == "all":
            repo_node_ids.append(repo["node_id"])
        elif visibility == "private" and repo.get("visibility") in {
            "private",
            "internal",
        }:
            repo_node_ids.append(repo["node_id"])
    return repo_node_ids


def _raw_collection(func: Any, *args: Any, **kwargs: Any):
    return getattr(func, "__wrapped__", func)(*args, **kwargs)


def _iter_org_contexts(ctx: SourceContext) -> Iterator[OrgContext]:
    if ctx.org_contexts:
        yield from ctx.org_contexts
    elif ctx.org_name:
        yield OrgContext(
            client=ctx.client,
            org_name=ctx.org_name,
            org_node_id=ctx.org_node_id,
        )


def _with_org_context(ctx: SourceContext, org_ctx: OrgContext) -> SourceContext:
    return SourceContext(
        client=org_ctx.client,
        org_name=org_ctx.org_name,
        org_node_id=org_ctx.org_node_id,
        enterprise_name=ctx.enterprise_name,
        enterprise_node_id=ctx.enterprise_node_id,
        auth_type=ctx.auth_type,
    )


def _iter_collection_contexts(ctx: SourceContext) -> Iterator[SourceContext]:
    for org_ctx in _iter_org_contexts(ctx):
        yield _with_org_context(ctx, org_ctx)


def _org_context_for(
    ctx: SourceContext, org_login: str | None, org_node_id: str | None = None
) -> SourceContext:
    for org_ctx in ctx.org_contexts:
        if org_login and org_ctx.org_name == org_login:
            return _with_org_context(ctx, org_ctx)
        if org_node_id and org_ctx.org_node_id == org_node_id:
            return _with_org_context(ctx, org_ctx)
    return SourceContext(
        client=ctx.client,
        org_name=org_login or ctx.org_name,
        org_node_id=org_node_id or ctx.org_node_id,
        enterprise_name=ctx.enterprise_name,
        enterprise_node_id=ctx.enterprise_node_id,
        auth_type=ctx.auth_type,
    )

def _graphql_object(page_data: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if not page_data:
        return {}
    root = page_data[0] or {}
    value = root.get(key) if isinstance(root, dict) else None
    return value if isinstance(value, dict) else {}


def _graphql_nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not connection:
        return []
    return [node for node in connection.get("nodes") or [] if isinstance(node, dict)]


def _graphql_edges(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not connection:
        return []
    return [edge for edge in connection.get("edges") or [] if isinstance(edge, dict)]


def _http_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) or getattr(exc, "status_code", None)



@configspec
class GithubCredentials(CredentialsConfiguration):
    org_name: str | None = None
    enterprise_name: str | None = None

    def auth(self):
        pass


@configspec
class GithubAppCredentials(GithubCredentials):
    client_id: str | None = None
    app_id: str | None = None
    key_path: str | None = None
    api_uri: str = "https://api.github.com"

    def auth(self) -> str:
        return "app"

    @property
    def header(self) -> str:
        github_access_token = create_github_jwt_session(
            org_name=self.org_name,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
            api_uri=self.api_uri,
        ).get_access_token()
        return github_access_token

    def header_for_installation(self, installation_id: int | str) -> str:
        return create_github_jwt_session(
            org_name=None,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=str(installation_id),
            api_uri=self.api_uri,
        ).get_access_token()

    def installations(self) -> list[dict[str, Any]]:
        return create_github_jwt_session(
            org_name=None,
            client_id=self.client_id,
            private_key_path=self.key_path,
            app_id=self.app_id,
            api_uri=self.api_uri,
        ).list_installations()


@configspec
class GithubTokenCredentials(GithubCredentials):
    token: str | None = None

    def auth(self) -> str:
        return "token"

    @property
    def header(self) -> str:
        return f"{self.token}"


@app.resource(name="enterprise", columns=Enterprise, parallelized=True)
def enterprise(data: dict[str, Any]):
    yield data


@app.resource(
    name="enterprise_organizations", columns=EnterpriseOrganization, parallelized=True
)
def enterprise_organizations(orgs: list[dict[str, Any]]):
    yield from orgs


@app.resource(name="enterprise_users", columns=EnterpriseUser, parallelized=True)
def enterprise_users(members: list[dict[str, Any]]):
    for member in members:
        user, _ = flatten_enterprise_member(
            member, member["enterprise_node_id"], member["enterprise_slug"]
        )
        if user:
            yield user


@app.resource(
    name="enterprise_managed_users", columns=EnterpriseManagedUser, parallelized=True
)
def enterprise_managed_users(members: list[dict[str, Any]]):
    for member in members:
        _, managed_user = flatten_enterprise_member(
            member, member["enterprise_node_id"], member["enterprise_slug"]
        )
        if managed_user:
            yield managed_user


@app.resource(name="enterprise_teams", columns=EnterpriseTeam, parallelized=True)
def enterprise_teams(ctx: SourceContext, enterprise_data: dict[str, Any]):
    enterprise_slug = _enterprise_required(ctx)
    try:
        for page in ctx.client.paginate(
            f"/enterprises/{enterprise_slug}/teams", params={"per_page": 100}
        ):
            for team in page:
                yield {
                    **team,
                    "enterprise_node_id": enterprise_data["id"],
                    "enterprise_slug": enterprise_slug,
                }
    except Exception:
        return


@app.transformer(
    name="enterprise_team_roles", columns=EnterpriseTeamRole, parallelized=True
)
def enterprise_team_roles(team: EnterpriseTeam):
    yield {
        "id": team.id,
        "name": team.name,
        "slug": team.slug,
        "enterprise_node_id": team.enterprise_node_id,
        "enterprise_slug": team.enterprise_slug,
    }


@app.transformer(
    name="enterprise_team_members", columns=EnterpriseTeamMember, parallelized=True
)
def enterprise_team_members(team: EnterpriseTeam, ctx: SourceContext):
    enterprise_slug = _enterprise_required(ctx)
    try:
        for page in ctx.client.paginate(
            f"/enterprises/{enterprise_slug}/teams/{team.id}/memberships",
            params={"per_page": 100},
        ):
            for member in page:
                node_id = member.get("node_id") or member.get("user", {}).get("node_id")
                if node_id:
                    yield {
                        **member,
                        "node_id": node_id,
                        "team_id": team.id,
                        "enterprise_node_id": team.enterprise_node_id,
                        "enterprise_slug": team.enterprise_slug,
                    }
    except Exception:
        return


@app.transformer(
    name="enterprise_team_organizations",
    columns=EnterpriseTeamOrganization,
    parallelized=True,
)
def enterprise_team_organizations(team: EnterpriseTeam, ctx: SourceContext):
    enterprise_slug = _enterprise_required(ctx)
    try:
        for page in ctx.client.paginate(
            f"/enterprises/{enterprise_slug}/teams/{team.id}/organizations",
            params={"per_page": 100},
        ):
            for org in page:
                node_id = org.get("node_id") or org.get("id")
                if node_id:
                    yield {
                        **org,
                        "node_id": node_id,
                        "team_id": team.id,
                        "projected_slug": team.slug,
                        "enterprise_node_id": team.enterprise_node_id,
                        "enterprise_slug": team.enterprise_slug,
                    }
    except Exception:
        return


@app.resource(name="enterprise_roles", columns=EnterpriseRole, parallelized=True)
def enterprise_roles(ctx: SourceContext, enterprise_data: dict[str, Any]):
    enterprise_slug = _enterprise_required(ctx)
    try:
        result = ctx.client.get(
            f"/enterprises/{enterprise_slug}/enterprise-roles"
        ).json()
    except Exception:
        return

    for role in result.get("roles", []):
        yield {
            **role,
            "enterprise_node_id": enterprise_data["id"],
            "enterprise_slug": enterprise_slug,
        }


@app.resource(name="enterprise_admin_roles", columns=EnterpriseRole, parallelized=True)
def enterprise_admin_roles(ctx: SourceContext, enterprise_data: dict[str, Any]):
    if ctx.auth_type != "token":
        return
    yield {
        "id": "owners",
        "name": "owners",
        "description": "Enterprise administrators discovered from ownerInfo.admins",
        "source": "Default",
        "permissions": [],
        "enterprise_node_id": enterprise_data["id"],
        "enterprise_slug": _enterprise_required(ctx),
    }


@app.transformer(
    name="enterprise_role_users", columns=EnterpriseRoleUser, parallelized=True
)
def enterprise_role_users(role: EnterpriseRole, ctx: SourceContext):
    if role.id == "owners":
        return
    enterprise_slug = _enterprise_required(ctx)
    try:
        for page in ctx.client.paginate(
            f"/enterprises/{enterprise_slug}/enterprise-roles/{role.id}/users",
            params={"per_page": 100},
        ):
            for user in page:
                if user.get("node_id"):
                    yield {
                        **user,
                        "role_id": role.id,
                        "enterprise_node_id": role.enterprise_node_id,
                        "enterprise_slug": role.enterprise_slug,
                    }
    except Exception:
        return


@app.transformer(
    name="enterprise_role_teams", columns=EnterpriseRoleTeam, parallelized=True
)
def enterprise_role_teams(role: EnterpriseRole, ctx: SourceContext):
    if role.id == "owners":
        return
    enterprise_slug = _enterprise_required(ctx)
    try:
        for page in ctx.client.paginate(
            f"/enterprises/{enterprise_slug}/enterprise-roles/{role.id}/teams",
            params={"per_page": 100},
        ):
            for team in page:
                if team.get("id"):
                    yield {
                        **team,
                        "role_id": role.id,
                        "enterprise_node_id": role.enterprise_node_id,
                        "enterprise_slug": role.enterprise_slug,
                    }
    except Exception:
        return


@app.resource(name="enterprise_admins", columns=EnterpriseRoleUser, parallelized=True)
def enterprise_admins(ctx: SourceContext, enterprise_data: dict[str, Any]):
    if ctx.auth_type != "token":
        return

    enterprise_slug = _enterprise_required(ctx)
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.admins.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_ADMINS_QUERY,
        "variables": {"slug": enterprise_slug, "count": 100, "after": None},
    }
    try:
        for page_data in ctx.client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            enterprise_data_page = _graphql_object(page_data, "enterprise")
            owner_info = enterprise_data_page.get("ownerInfo") or {}
            for edge in _graphql_edges(owner_info.get("admins")):
                node = edge.get("node")
                if node and node.get("id"):
                    yield {
                        "node_id": node["id"],
                        "login": node.get("login"),
                        "assignment": "direct",
                        "role_id": "owners",
                        "enterprise_node_id": enterprise_data["id"],
                        "enterprise_slug": enterprise_slug,
                    }
    except Exception:
        return


@app.resource(
    name="enterprise_saml_provider", columns=EnterpriseSamlProvider, parallelized=True
)
def enterprise_saml_provider(provider: dict[str, Any] | None):
    if provider:
        yield provider


@app.resource(
    name="enterprise_external_identities",
    columns=EnterpriseExternalIdentity,
    parallelized=True,
)
def enterprise_external_identities(identities: list[dict[str, Any]]):
    yield from identities


@app.resource(name="organizations", columns=Organization, parallelized=True)
def organizations(ctx: SourceContext):
    """Fetch organization details, actions permissions, and org roles from GitHub API.

    Yields organization data to the `organizations` table, custom and default org roles
    to the `org_roles` table, and per-role user/team assignments to `org_role_members`
    and `org_role_teams` tables via dlt.mark.with_table_name().

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Organization (Organization): Organization, org role, member, and team records.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(organizations, org_ctx)
        return

    org_data = ctx.client.get(f"/orgs/{ctx.org_name}").json()
    ctx.org_node_id = org_data.get("node_id")

    actions = ctx.client.get(f"/orgs/{ctx.org_name}/actions/permissions").json()
    self_hosted_runners = ctx.client.get(
        f"/orgs/{ctx.org_name}/actions/permissions/self-hosted-runners"
    ).json()
    workflow_perms = ctx.client.get(
        f"/orgs/{ctx.org_name}/actions/permissions/workflow"
    ).json()

    org_data["actions_enabled_repositories"] = actions.get("enabled_repositories")
    org_data["actions_allowed_actions"] = actions.get("allowed_actions")
    org_data["actions_sha_pinning_required"] = actions.get("sha_pinning_required")
    org_data["self_hosted_runners_enabled_repositories"] = self_hosted_runners.get(
        "enabled_repositories"
    )
    org_data["default_workflow_permissions"] = workflow_perms.get(
        "default_workflow_permissions"
    )
    org_data["can_approve_pull_request_reviews"] = workflow_perms.get(
        "can_approve_pull_request_reviews"
    )

    yield {**org_data, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.resource(name="org_roles", columns=OrgRole, parallelized=True)
def org_roles(ctx: SourceContext, orgs: list[dict] | None = None):
    """Fetch default and custom organization roles from the GitHub API.

    Yields the built-in 'owners' and 'members' roles, then fetches any custom
    organization roles from the API.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.
        orgs (list[dict]): Organization records from the organizations resource.

    Yields:
        OrgRole (OrgRole): Organization role record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            org_rows = [
                org
                for org in orgs or []
                if org.get("login") == org_ctx.org_name
                or org.get("node_id") == org_ctx.org_node_id
            ]
            if not org_rows:
                org_rows = list(_raw_collection(organizations, org_ctx))
            yield from _raw_collection(org_roles, org_ctx, org_rows)
        return

    if orgs is None:
        orgs = list(_raw_collection(organizations, ctx))
    org = Organization(**orgs[0])

    yield {
        "id": 1,
        "name": "owners",
        "type": "default",
        "base_role": "admin",
        "created_at": datetime.now().isoformat(),
        "permissions": [],
        "org_node_id": org.node_id,
        "org_login": org.login,
    }

    yield {
        "id": 2,
        "name": "members",
        "type": "default",
        "created_at": datetime.now().isoformat(),
        "base_role": org.default_repository_permission,
        "permissions": [],
        "org_node_id": org.node_id,
        "org_login": org.login,
    }

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/organization-roles", params={"per_page": 100}
    ):
        for role in page:
            yield {
                **role,
                "type": "custom",
                "org_node_id": org.node_id,
                "org_login": org.login,
            }


@app.transformer(name="org_role_teams", columns=OrgRoleTeam, parallelized=True)
def org_role_teams(role: OrgRole, ctx: SourceContext):
    """Fetch teams assigned to a custom organization role.

    Only fetches team assignments for custom roles (not default built-in roles).

    Args:
        role (OrgRole): The organization role to fetch team assignments for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        OrgRoleTeam (OrgRoleTeam): Team-to-org-role assignment record.
    """

    role_ctx = _org_context_for(ctx, role.org_login, role.org_node_id)
    if role.type == "custom":
        for page in role_ctx.client.paginate(
            f"/orgs/{role_ctx.org_name}/organization-roles/{role.id}/teams"
        ):
            for team in page:
                yield {
                    "org_role_id": role.id,
                    "org_role_name": role.name,
                    "org_node_id": role.org_node_id,
                    "org_login": role.org_login,
                    **team,
                }


@app.transformer(name="org_role_members", columns=OrgRoleMember, parallelized=True)
def org_role_members(role: OrgRole, ctx: SourceContext):
    """Fetch users assigned to a custom organization role.

    Only fetches user assignments for custom roles (not default built-in roles).

    Args:
        role (OrgRole): The organization role to fetch user assignments for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        OrgRoleMember (OrgRoleMember): User-to-org-role assignment record.
    """
    role_ctx = _org_context_for(ctx, role.org_login, role.org_node_id)
    if role.type == "custom":
        for page in role_ctx.client.paginate(
            f"/orgs/{role_ctx.org_name}/organization-roles/{role.id}/users"
        ):
            for user in page:
                yield {
                    **user,
                    "org_role_name": role.name,
                    "org_role_id": role.id,
                    "org_node_id": role.org_node_id,
                    "org_login": role.org_login,
                }


@app.resource(name="app_installations", columns=AppInstallation, parallelized=True)
def app_installations(ctx: SourceContext):
    """Fetch GitHub App installations for the organization.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        AppInstallation (AppInstallation): App installation record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(app_installations, org_ctx)
        return

    for page in ctx.client.paginate(f"/orgs/{ctx.org_name}/installations"):
        for item in page:
            yield {**item, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.transformer(name="applications", columns=App, parallelized=True)
def applications(app_install: AppInstallation, ctx: SourceContext):
    """Fetch full GitHub App details for an installed app.

    Args:
        app_install (AppInstallation): The app installation to fetch app details for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        App (App): GitHub App record.
    """
    app_ctx = _org_context_for(ctx, app_install.org_login, app_install.org_node_id)
    app_slug = app_install.app_slug if app_install.app_slug else app_install.app_id
    if app_install.id:
        app_data = app_ctx.client.get(f"/apps/{app_slug}").json()
        if app_data.get("node_id"):
            yield {
                **app_data,
                "slug": app_slug,
                "org_node_id": app_install.org_node_id,
                "org_login": app_install.org_login,
            }


@app.resource(name="users", columns=User, parallelized=True)
def users(ctx: SourceContext) -> Iterator[dict[str, Any]]:
    """Fetch organization members from GitHub GraphQL API, including their org role.

    Uses the membersWithRole connection to retrieve user details (login, name, email,
    company) and organization role (ADMIN or MEMBER) in a single paginated query.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        User (User): User record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(users, org_ctx)
        return

    paginator = GraphQLCursorPaginator(
        page_info_path="data.organization.membersWithRole.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": MEMBERS_WITH_ROLE_QUERY,
        "variables": {"login": ctx.org_name, "count": 100, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        org_data = _graphql_object(page_data, "organization")
        for edge in _graphql_edges(org_data.get("membersWithRole")):
            node = edge.get("node") or {}
            yield {
                **node,
                **edge,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.resource(name="teams", columns=Team, parallelized=True)
def teams(ctx: SourceContext):
    """Fetch teams and team member assignments from GitHub GraphQL API.

    Uses the Organization.teams connection with nested IMMEDIATE members to fetch
    team info and member-role assignments in a single paginated query. Teams with
    more than 100 members are followed up with additional member pagination queries.

    Yields team records to the `teams` table and member-role records to the
    `team_members` table via dlt.mark.with_table_name().

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Team (Team): Team record lol!.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(teams, org_ctx)
        return

    paginator = GraphQLCursorPaginator(
        page_info_path="data.organization.teams.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": TEAMS_QUERY,
        "variables": {"login": ctx.org_name, "count": 100, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        org_data = _graphql_object(page_data, "organization")
        for team in _graphql_nodes(org_data.get("teams")):
            yield {
                **team,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.transformer(name="team_roles", columns=TeamRole, parallelized=True)
def team_roles(team: Team):
    """Yield the two built-in team roles (members and maintainers) for a team.

    Args:
        team (Team): The team to generate role records for.

    Yields:
        TeamRole (TeamRole): Team role records (one for members, one for maintainers).
    """
    for role_type in ("members", "maintainers"):
        yield {
            "type": role_type,
            "team_node_id": team.node_id,
            "team_name": team.name,
            "team_slug": team.slug,
            "org_node_id": team.org_node_id,
            "org_login": team.org_login,
        }


@app.transformer(name="team_members", columns=TeamMember, parallelized=True)
def team_members(team: Team, ctx: SourceContext):
    """Fetch team member assignments including their role (member or maintainer).

    Processes members from the initial team query and handles overflow pagination
    for teams with more than 100 members via a follow-up GraphQL query.

    Args:
        team (Team): The team to fetch member assignments for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        TeamMember (TeamMember): Team member assignment record.
    """
    team_ctx = _org_context_for(ctx, team.org_login, team.org_node_id)
    for member in team.members.edges:
        yield {
            "team_id": team.id,
            "id": member.node.id,
            "login": member.node.login,
            "role": member.role,
            "org_node_id": team.org_node_id,
            "org_login": team.org_login,
        }

    paginator = GraphQLCursorPaginator(
        page_info_path="data.organization.team.members.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )

    if team.members.page_info.has_next_page:
        data = {
            "query": TEAM_MEMBERS_OVERFLOW_QUERY,
            "variables": {
                "login": team_ctx.org_name,
                "count": 100,
                "after": team.members.page_info.end_cursor,
                "slug": team.slug,
            },
        }
        for page_data in team_ctx.client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            org_data = _graphql_object(page_data, "organization")
            team_data = org_data.get("team") or {}
            for member in _graphql_edges(team_data.get("members")):
                yield {
                    "team_id": team.id,
                    "id": member["node"]["id"],
                    "login": member["node"]["login"],
                    "role": member["role"],
                    "org_node_id": team.org_node_id,
                    "org_login": team.org_login,
                }


@app.resource(name="actions_permissions", columns=ActionPermission, parallelized=True)
def actions_permissions(ctx: SourceContext):
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(actions_permissions, org_ctx)
        return

    actions = ctx.client.get(f"/orgs/{ctx.org_name}/actions/permissions").json()
    yield actions


@app.resource(name="repositories", columns=Repository, parallelized=True)
def repositories(ctx: SourceContext):
    """Fetch repositories for the organization.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Repository (Repository): Repository record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(repositories, org_ctx)
        return

    actions = ctx.client.get(f"/orgs/{ctx.org_name}/actions/permissions").json()
    runner_settings = ctx.client.get(
        f"/orgs/{ctx.org_name}/actions/permissions/self-hosted-runners"
    ).json()

    enabled_repo_ids: set[str] | None = None
    if actions.get("enabled_repositories") == "selected":
        enabled_repo_ids = set()
        for page in ctx.client.paginate(
            f"/orgs/{ctx.org_name}/actions/permissions/repositories",
            params={"per_page": 100},
            data_selector="repositories",
        ):
            enabled_repo_ids.update(
                repo["node_id"] for repo in page if repo.get("node_id")
            )

    runner_enabled_repo_ids: set[str] | None = None
    if runner_settings.get("enabled_repositories") == "selected":
        runner_enabled_repo_ids = set()
        for page in ctx.client.paginate(
            f"/orgs/{ctx.org_name}/actions/permissions/self-hosted-runners/repositories",
            params={"per_page": 100},
            data_selector="repositories",
        ):
            runner_enabled_repo_ids.update(
                repo["node_id"] for repo in page if repo.get("node_id")
            )

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/repos", params={"per_page": 100}
    ):
        for repo in page:
            repo_node_id = repo.get("node_id")
            actions_enabled = actions.get("enabled_repositories") == "all" or (
                enabled_repo_ids is not None and repo_node_id in enabled_repo_ids
            )
            self_hosted_runners_enabled = runner_settings.get(
                "enabled_repositories"
            ) == "all" or (
                runner_enabled_repo_ids is not None
                and repo_node_id in runner_enabled_repo_ids
            )
            yield {
                **repo,
                "actions_enabled": actions_enabled,
                "self_hosted_runners_enabled": self_hosted_runners_enabled,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.transformer(
    name="repo_role_assignments", columns=RepoRoleAssignment, parallelized=True
)
def repo_role_assignments(
    repo: Repository, ctx: SourceContext, roles: list[dict] | None = None
) -> Iterator[dict[str, Any]]:
    """Fetch collaborator and team role assignments for each repository.

    For each repo, fetches direct collaborators (affiliation=direct) and team access,
    mapping the GitHub permission/role_name to a deterministic repo role node ID
    (base64 of "{repo_node_id}_{role_short_name}") that matches the IDs emitted by
    the `repositories` resource.

    API endpoints:
    - GET /repos/{org}/{repo}/collaborators?affiliation=direct
    - GET /repos/{org}/{repo}/teams

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        RepoRoleAssignment (RepoRoleAssignment): Role assignment records for direct collaborators and teams.
    """

    repo_ctx = _org_context_for(ctx, repo.org_login or repo.owner_name, repo.org_node_id)
    if roles is None:
        roles = list(_raw_collection(repository_roles_base, repo_ctx))
    repo_node_id = repo.node_id
    repo_name = repo.name
    custom_roles = {
        role["name"]: BaseRepoRole(**role)
        for role in roles
        if not role.get("org_login") or role.get("org_login") == repo_ctx.org_name
    }

    for collab_page in repo_ctx.client.paginate(
        f"/repos/{repo_ctx.org_name}/{repo_name}/collaborators",
        params={"affiliation": "direct", "per_page": 100},
    ):
        for collaborator in collab_page:
            role = collaborator.get("role_name", "")
            custom_role = custom_roles.get(role)
            yield {
                **collaborator,
                "assignee_type": "user",
                "repo_node_id": repo_node_id,
                "repo_name": repo_name,
                "role_name": role,
                "base_role": custom_role.base_role if custom_role else None,
                "role_permissions": custom_role.permissions if custom_role else [],
            }

    # Team access
    for team_page in repo_ctx.client.paginate(
        f"/repos/{repo_ctx.org_name}/{repo_name}/teams",
        params={"per_page": 100},
    ):
        for team in team_page:
            permission: str = team.get("permission", "")
            role = TEAM_PERMISSION_MAP.get(permission, permission)
            custom_role = custom_roles.get(role)
            yield {
                **team,
                "assignee_type": "team",
                "repo_node_id": repo_node_id,
                "repo_name": repo_name,
                "role_name": role,
                "base_role": custom_role.base_role if custom_role else None,
                "role_permissions": custom_role.permissions if custom_role else [],
            }


@app.resource(name="repository_roles_base", parallelized=True, columns=BaseRepoRole)
def repository_roles_base(ctx: SourceContext):
    """Fetch custom repository roles from GitHub API.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        dict: Raw custom repository role records from the GitHub API.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(repository_roles_base, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/custom-repository-roles", params={"per_page": 100}
    ):
        for role in page:
            yield {**role, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.transformer(name="repo_roles", columns=RepoRole, parallelized=True)
def repository_roles(repository: Repository, ctx: SourceContext):
    """Yield default and custom repository role records for a repository.

    Emits the five built-in default roles (read, triage, write, maintain, admin) and
    any custom repository roles defined at the organization level.

    Args:
        repository (Repository): The repository to generate role records for.
        roles (list[dict]): Custom role definitions from repository_roles_base.

    Yields:
        RepoRole (RepoRole): Repository role record.
    """
    for idx, role in enumerate(DEFAULT_REPO_ROLES):
        yield {
            "id": idx,
            "name": role["name"],
            "type": "default",
            "base_role": role["base_role"],
            "permissions": [],
            "repository_full_name": repository.full_name,
            "repository_name": repository.name,
            "repository_node_id": repository.node_id,
            "repository_visibility": repository.visibility,
            "org_node_id": repository.org_node_id or repository.owner_id,
            "org_login": repository.org_login or repository.owner_name,
        }

    repo_ctx = _org_context_for(
        ctx, repository.org_login or repository.owner_name, repository.org_node_id
    )
    roles = list(_raw_collection(repository_roles_base, repo_ctx))

    for role in roles:
        if role.get("org_login") and role.get("org_login") != repository.org_login:
            continue
        role = BaseRepoRole(**role)
        yield {
            "id": role.id,
            "name": role.name,
            "type": "custom",
            "base_role": role.base_role,
            "permissions": role.permissions,
            "repository_full_name": repository.full_name,
            "repository_name": repository.name,
            "repository_node_id": repository.node_id,
            "repository_visibility": repository.visibility,
            "org_node_id": repository.org_node_id or repository.owner_id,
            "org_login": repository.org_login or repository.owner_name,
        }


@app.resource(name="repositories_graphql", columns=RepositoryQL, parallelized=True)
def repositories_graphql(ctx: SourceContext):
    """Fetch repositories with branch and protection rule metadata via GraphQL.

    Uses the organization repositories connection to retrieve branches with their
    associated branch protection rule IDs, used as input for the branches and
    branch_protection_rules transformers.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        RepositoryQL (RepositoryQL): Repository record with nested branch ref data.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(repositories_graphql, org_ctx)
        return

    paginator = GraphQLCursorPaginator(
        page_info_path="data.organization.repositories.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": REPO_REFS_QUERY,
        "variables": {"login": ctx.org_name, "count": 100, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        org_data = _graphql_object(page_data, "organization")
        for repo in _graphql_nodes(org_data.get("repositories")):
            yield {
                **repo,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.transformer(name="branches", columns=Branch, parallelized=True)
def branches(repository: RepositoryQL, ctx: SourceContext):
    """Yield branches for a repository.

    Processes branches from the initial repository query and handles overflow
    pagination for repos with more than 100 branches via a follow-up GraphQL query.

    Args:
        repository (RepositoryQL): The repository with refs data.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Branch (Branch): Branch record.
    """
    repo_ctx = _org_context_for(ctx, repository.org_login, repository.org_node_id)
    paginator = GraphQLCursorPaginator(
        page_info_path="data.organization.repository.refs.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )

    for branch in repository.refs.nodes:
        yield {
            **branch.model_dump(),
            "repository_node_id": repository.id,
            "repository_name": repository.name,
            "org_node_id": repository.org_node_id,
            "org_login": repository.org_login,
        }

    if repository.refs.page_info.has_next_page:
        data = {
            "query": REF_OVERFLOW_QUERY,
            "variables": {
                "owner": repo_ctx.org_name,
                "count": 100,
                "after": repository.refs.page_info.end_cursor,
                "name": repository.name,
            },
        }

        for page_data in repo_ctx.client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            repo_data = _graphql_object(page_data, "repository")
            for branch in _graphql_nodes(repo_data.get("refs")):
                yield {
                    **branch,
                    "repository_node_id": repository.id,
                    "repository_name": repository.name,
                    "org_node_id": repository.org_node_id,
                    "org_login": repository.org_login,
                }


@app.transformer(
    name="branch_protection_rules", columns=BranchProtectionRule, parallelized=True
)
def branch_protection_rules(repository: RepositoryQL, ctx: SourceContext):
    """Batch-fetch branch protection rule details for a repository.

    For a given repository, extracts all unique protection rule IDs from its branches
    (including overflow pagination), batch-fetches the full rule details (settings, allowances),
    and yields BranchProtectionRule objects.

    Args:
        repository (RepositoryQL): The repository with refs data (can have nested branches).
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        BranchProtectionRule (BranchProtectionRule): Protection rule record with full details.
    """
    repo_ctx = _org_context_for(ctx, repository.org_login, repository.org_node_id)
    # Note: multiple branches can reference the same branch protection rule
    # so use a set to prevent duplicates
    rule_ids_seen: set[str] = set()
    for branch in repository.refs.nodes:
        if branch.branch_protection_rule:
            rule_id = branch.branch_protection_rule.get("id")
            if rule_id:
                rule_ids_seen.add(rule_id)

    rule_ids_list = list(rule_ids_seen)
    for i in range(0, len(rule_ids_list), 100):
        rules_chunk = rule_ids_list[i : i + 100]
        if rules_chunk:
            data = {"query": PROTECTION_RULES_QUERY, "variables": {"ids": rules_chunk}}
            response = repo_ctx.client.post(
                f"{repo_ctx.client.base_url}/graphql", json=data
            ).json()
            for rule in (response.get("data") or {}).get("nodes", []):
                if not rule:
                    continue
                yield {
                    **rule,
                    "repository_node_id": repository.id,
                    "repository_name": repository.name,
                    "org_node_id": repository.org_node_id,
                    "org_login": repository.org_login,
                }


@app.transformer(name="workflows", columns=Workflow, parallelized=True)
def workflows(repo: Repository, ctx: SourceContext):
    """Fetch GitHub Actions workflows for a single repository.

    Args:
        repo (Repository): The repository to fetch workflows for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Workflow (Workflow): An active workflow record.
    """
    repo_ctx = _org_context_for(ctx, repo.org_login, repo.org_node_id)
    for page in repo_ctx.client.paginate(
        f"/repos/{repo.full_name}/actions/workflows", params={"per_page": 100}
    ):
        for workflow in page:
            # TODO: Check if we should only store active workflows
            if workflow.get("state") == "active":
                yield {
                    **workflow,
                    "repository_name": repo.name,
                    "repository_node_id": repo.node_id,
                    "org_node_id": repo.org_node_id,
                    "org_login": repo.org_login,
                }


@app.transformer(name="environments", columns=Environment, parallelized=True)
def environments(repo: Repository, ctx: SourceContext):
    """Fetch deployment environments for a repository.

    Args:
        repo (Repository): The repository to fetch environments for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        Environment (Environment): Deployment environment record.
    """
    repo_ctx = _org_context_for(ctx, repo.org_login, repo.org_node_id)
    full_name = repo.full_name
    repo_name = repo.name
    repo_node_id = repo.node_id
    for page in repo_ctx.client.paginate(
        f"/repos/{full_name}/environments",
        params={"per_page": 100},
        data_selector="environments",
    ):
        for env in page:
            yield {
                **env,
                "repository_name": repo_name,
                "repository_full_name": full_name,
                "repository_node_id": repo_node_id,
                "org_node_id": repo.org_node_id,
                "org_login": repo.org_login,
            }


@app.resource(name="runner_groups", columns=RunnerGroup, parallelized=True)
def runner_groups(ctx: SourceContext):
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(runner_groups, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/actions/runner-groups",
        params={"per_page": 100},
        data_selector="runner_groups",
    ):
        for group in page:
            yield {**group, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.resource(name="org_runners", columns=OrgRunner, parallelized=True)
def org_runners(ctx: SourceContext):
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(org_runners, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/actions/runners",
        params={"per_page": 100},
        data_selector="runners",
    ):
        for runner in page:
            yield {**runner, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.resource(
    name="org_runner_group_memberships",
    columns=OrgRunnerGroupMembership,
    parallelized=True,
)
def org_runner_group_memberships(ctx: SourceContext, repos: list | None = None):
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            org_repos = [
                repo
                for repo in repos or []
                if repo.get("org_login") == org_ctx.org_name
                or repo.get("org_node_id") == org_ctx.org_node_id
            ]
            yield from _raw_collection(org_runner_group_memberships, org_ctx, org_repos)
        return

    if repos is None:
        repos = list(_raw_collection(repositories, ctx))

    for group_page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/actions/runner-groups",
        params={"per_page": 100},
        data_selector="runner_groups",
    ):
        for group in group_page:
            accessible_repo_node_ids = _runner_group_repo_node_ids(group, ctx, repos)
            try:
                for runner_page in ctx.client.paginate(
                    f"/orgs/{ctx.org_name}/actions/runner-groups/{group['id']}/runners",
                    params={"per_page": 100},
                    data_selector="runners",
                ):
                    for runner in runner_page:
                        yield {
                            "runner_group_id": group["id"],
                            "runner_id": runner["id"],
                            "accessible_repo_node_ids": accessible_repo_node_ids,
                            "org_node_id": ctx.org_node_id,
                            "org_login": ctx.org_name,
                        }
            except Exception:
                continue


@app.transformer(name="repo_runners", columns=RepoRunner, parallelized=True)
def repo_runners(repo: Repository, ctx: SourceContext):
    repo_ctx = _org_context_for(ctx, repo.org_login, repo.org_node_id)
    if not repo.self_hosted_runners_enabled:
        return
    for page in repo_ctx.client.paginate(
        f"/repos/{repo.full_name}/actions/runners",
        params={"per_page": 100},
        data_selector="runners",
    ):
        for runner in page:
            yield {
                **runner,
                "repository_name": repo.name,
                "repository_node_id": repo.node_id,
                "repository_full_name": repo.full_name,
                "org_node_id": repo.org_node_id,
                "org_login": repo.org_login,
            }


@app.transformer(
    name="environment_variables", columns=EnvironmentVariable, parallelized=True
)
def environment_variables(environment: Environment, ctx: SourceContext):
    """Fetch variables for a deployment environment.

    Args:
        environment (Environment): The environment to fetch variables for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        EnvironmentVariable (EnvironmentVariable): Environment variable record.
    """
    env_ctx = _org_context_for(ctx, environment.org_login, environment.org_node_id)
    env_name = environment.name
    env_node_id = environment.node_id

    full_repo_name = environment.repository_full_name
    repo_name = environment.repository_name
    repo_node_id = environment.repository_node_id

    for page in env_ctx.client.paginate(
        f"/repos/{full_repo_name}/environments/{env_name}/variables"
    ):
        for item in page:
            yield {
                **item,
                "environment_node_id": env_node_id,
                "environment_name": env_name,
                "repository_name": repo_name,
                "repository_node_id": repo_node_id,
                "org_node_id": environment.org_node_id,
                "org_login": environment.org_login,
            }


@app.transformer(
    name="environment_branch_policies",
    columns=EnvironmentBranchPolicy,
    parallelized=True,
)
def environment_branch_policies(environment: Environment, ctx: SourceContext):
    """Fetch deployment branch policies for an environment.

    Only fetches policies when the environment has custom branch policies configured.

    Args:
        environment (Environment): The environment to fetch branch policies for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        EnvironmentBranchPolicy (EnvironmentBranchPolicy): Environment branch policy record.
    """
    env_ctx = _org_context_for(ctx, environment.org_login, environment.org_node_id)
    has_custom = environment.deployment_branch_policy
    if has_custom:
        full_repo_name = environment.repository_full_name
        repo_name = environment.repository_name
        repo_node_id = environment.repository_node_id
        env_name = environment.name
        env_node_id = environment.node_id
        try:
            for page in env_ctx.client.paginate(
                f"/repos/{full_repo_name}/environments/{env_name}/deployment-branch-policies"
            ):
                for policy in page:
                    yield {
                        **policy,
                        "environment_node_id": env_node_id,
                        "environment_name": env_name,
                        "repository_name": repo_name,
                        "repository_node_id": repo_node_id,
                        "org_node_id": environment.org_node_id,
                        "org_login": environment.org_login,
                    }
        except Exception as exc:
            if _http_status_code(exc) == 404:
                return
            raise


@app.transformer(
    name="environment_secrets", columns=EnvironmentSecret, parallelized=True
)
def environment_secrets(environment: Environment, ctx: SourceContext):
    """Fetch secrets for a deployment environment.

    Args:
        environment (Environment): The environment to fetch secrets for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        EnvironmentSecret (EnvironmentSecret): Environment secret record.
    """
    env_ctx = _org_context_for(ctx, environment.org_login, environment.org_node_id)
    repo_name = environment.repository_name
    repo_node_id = environment.repository_node_id
    full_repo_name = environment.repository_full_name

    env_name = environment.name
    env_node_id = environment.node_id
    for page in env_ctx.client.paginate(
        f"/repos/{full_repo_name}/environments/{env_name}/secrets"
    ):
        for secret in page:
            yield {
                **secret,
                "repository_name": repo_name,
                "repository_node_id": repo_node_id,
                "environment_name": env_name,
                "environment_node_id": env_node_id,
                "org_node_id": environment.org_node_id,
                "org_login": environment.org_login,
            }


@app.resource(name="organization_secrets", columns=OrgSecret, parallelized=True)
def organization_secrets(ctx: SourceContext):
    """Fetch organization-level GitHub Actions secrets and variables with repository access.

    Yields records to the following tables:
    - organization_secrets: org-level secret metadata
    - organization_variables: org-level variable metadata (with values)
    - org_secret_repo_access: junction table linking secrets to accessible repos
    - org_variable_repo_access: junction table linking variables to accessible repos

    Visibility semantics:
    - "all": all org repos have access
    - "private": private and internal repos only
    - "selected": specific repos fetched via API

    API Reference:
    - https://docs.github.com/en/rest/actions/secrets#list-organization-secrets
    - https://docs.github.com/en/rest/actions/variables#list-organization-variables

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        OrgSecret (OrgSecret): Organization secret record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(organization_secrets, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/actions/secrets", params={"per_page": 100}
    ):
        for item in page:
            yield {**item, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.transformer(
    name="selected_organization_secrets", columns=SelectedOrgSecret, parallelized=True
)
def selected_organization_secrets(secret: OrgSecret, ctx: SourceContext):
    """Fetch repositories that a 'selected' visibility organization secret is accessible to.

    Only fetches repository access for secrets with visibility set to 'selected'.

    Args:
        secret (OrgSecret): The organization secret to fetch repository access for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        SelectedOrgSecret (SelectedOrgSecret): Secret-to-repository access record.
    """
    secret_ctx = _org_context_for(ctx, secret.org_login, secret.org_node_id)
    if secret.visibility == "selected":
        for page in secret_ctx.client.paginate(
            f"/orgs/{secret_ctx.org_name}/actions/secrets/{secret.name}/repositories",
            params={"per_page": 100},
        ):
            for repo in page:
                yield {
                    "name": secret.name,
                    "repository_full_name": repo["full_name"],
                    "repository_node_id": repo["node_id"],
                    "org_node_id": secret.org_node_id,
                    "org_login": secret.org_login,
                }


@app.resource(name="organization_variables", columns=OrgVariable, parallelized=True)
def organization_variables(ctx: SourceContext):
    """Fetch organization-level GitHub Actions variables.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        OrgVariable (OrgVariable): Organization variable record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(organization_variables, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/actions/variables", params={"per_page": 100}
    ):
        for item in page:
            yield {**item, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.transformer(
    name="selected_organization_variables",
    columns=SelectedOrgVariable,
    parallelized=True,
)
def selected_organization_variables(variable: OrgVariable, ctx: SourceContext):
    """Fetch repositories that a 'selected' visibility organization variable is accessible to.

    Only fetches repository access for variables with visibility set to 'selected'.

    Args:
        variable (OrgVariable): The organization variable to fetch repository access for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        SelectedOrgVariable (SelectedOrgVariable): Variable-to-repository access record.
    """
    variable_ctx = _org_context_for(ctx, variable.org_login, variable.org_node_id)
    if variable.visibility == "selected":
        for page in variable_ctx.client.paginate(
            f"/orgs/{variable_ctx.org_name}/actions/variables/{variable.name}/repositories",
            params={"per_page": 100},
        ):
            for repo in page:
                yield {
                    "name": variable.name,
                    "repository_node_id": repo["node_id"],
                    "org_node_id": variable.org_node_id,
                    "org_login": variable.org_login,
                }


@app.transformer(name="repository_secrets", columns=RepoSecret, parallelized=True)
def repository_secrets(repo: Repository, ctx: SourceContext):
    """Fetch repository-level GitHub Actions secrets for each repository.

    Args:
        repo (dict): Individual repository data dictionary from repositories() resource.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        RepoSecret (RepoSecret): Repository secret record.
    """
    repo_ctx = _org_context_for(ctx, repo.org_login, repo.org_node_id)
    for page in repo_ctx.client.paginate(
        f"/repos/{repo.full_name}/actions/secrets", params={"per_page": 100}
    ):
        for secret in page:
            yield {
                **secret,
                "repository_name": repo.full_name,
                "repository_node_id": repo.node_id,
                "org_node_id": repo.org_node_id,
                "org_login": repo.org_login,
            }


@app.transformer(name="repository_variables", columns=RepoVariable, parallelized=True)
def repository_variables(repo: Repository, ctx: SourceContext):
    """Fetch repository-level GitHub Actions variables for each repository.

    API Reference:
    - https://docs.github.com/en/rest/actions/variables#list-repository-variables

    Args:
        repo (Repository): Individual repository data (as model) from repositories() resource.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        RepoVariable (RepoVariable): Repository variable record.
    """
    repo_ctx = _org_context_for(ctx, repo.org_login, repo.org_node_id)
    for page in repo_ctx.client.paginate(
        f"/repos/{repo.full_name}/actions/variables", params={"per_page": 100}
    ):
        for variable in page:
            yield {
                **variable,
                "repository_name": repo.full_name,
                "repository_node_id": repo.node_id,
                "org_node_id": repo.org_node_id,
                "org_login": repo.org_login,
            }


@app.resource(
    name="secret_scanning_alerts", columns=SecretScanningAlert, parallelized=True
)
def secret_scanning_alerts(ctx: SourceContext):
    """Fetch secret scanning alerts for the organization.

    Produces a flat record per alert with a synthetic node_id.

    API Reference:
    - https://docs.github.com/en/rest/secret-scanning/secret-scanning#list-secret-scanning-alerts-for-an-organization

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        SecretScanningAlert (SecretScanningAlert): A secret scanning alert.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(secret_scanning_alerts, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/secret-scanning/alerts", params={"per_page": 100}
    ):
        for alert in page:
            valid_token_user_node_id: str | None = None
            secret = alert.get("secret")
            if (
                alert.get("state") == "open"
                and alert.get("secret_type") == "github_personal_access_token"
                and secret
            ):
                try:
                    resp = requests.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"Bearer {secret}"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        valid_token_user_node_id = resp.json().get("node_id")
                except Exception:
                    pass

            yield {
                **alert,
                "valid_token_user_node_id": valid_token_user_node_id,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.resource(
    name="personal_access_tokens", columns=PersonalAccessToken, parallelized=True
)
def personal_access_tokens(ctx: SourceContext):
    """Fetch fine-grained PATs granted access to the organization.

    API Reference:
    - https://docs.github.com/en/rest/orgs/personal-access-tokens#list-fine-grained-personal-access-tokens-with-access-to-organization-resources
    - https://docs.github.com/en/rest/orgs/personal-access-tokens#list-repositories-a-fine-grained-personal-access-token-has-access-to

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        PersonalAccessToken (PersonalAccessToken): Fine-grained personal access token record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(personal_access_tokens, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/personal-access-tokens", params={"per_page": 100}
    ):
        for pat in page:
            yield {**pat, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


@app.transformer(name="pat_repo_access", columns=PatRepoAccess, parallelized=True)
def pat_repo_access(pat: PersonalAccessToken | dict[str, Any], ctx: SourceContext):
    """Fetch repositories a fine-grained PAT has access to within the organization.

    Args:
        pat (PersonalAccessToken): The personal access token to fetch repository access for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        PatRepoAccess (PatRepoAccess): PAT-to-repository access record.
    """
    pat_id = pat["id"] if isinstance(pat, dict) else pat.id
    org_node_id = pat.get("org_node_id") if isinstance(pat, dict) else pat.org_node_id
    org_login = pat.get("org_login") if isinstance(pat, dict) else pat.org_login
    pat_ctx = _org_context_for(ctx, org_login, org_node_id)

    for page in pat_ctx.client.paginate(
        f"/orgs/{pat_ctx.org_name}/personal-access-tokens/{pat_id}/repositories",
        params={"per_page": 100},
    ):
        for item in page:
            yield {
                "pat_id": pat_id,
                "org_node_id": org_node_id,
                "org_login": org_login,
                **item,
            }


@app.resource(
    name="personal_access_token_requests",
    columns=PersonalAccessTokenRequest,
    parallelized=True,
)
def personal_access_token_requests(ctx: SourceContext):
    """Fetch pending fine-grained PAT requests for organization resources.

    API Reference:
    - https://docs.github.com/en/rest/orgs/personal-access-token-requests#list-requests-to-access-organization-resources-with-fine-grained-personal-access-tokens

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        PersonalAccessTokenRequest (PersonalAccessTokenRequest): PAT request record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(personal_access_token_requests, org_ctx)
        return

    for page in ctx.client.paginate(
        f"/orgs/{ctx.org_name}/personal-access-token-requests",
        params={"per_page": 100},
    ):
        for request in page:
            yield {
                **request,
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }


@app.resource(name="saml_provider", columns=SamlProvider, parallelized=True)
def saml_provider(ctx: SourceContext):
    """Fetch the SAML identity provider for the organization.

    Yields records to the saml_provider table only. External identities are yielded
    separately by the external_identities transformer.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        SamlProvider (SamlProvider): SAML provider record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(saml_provider, org_ctx)
        return

    data = {
        "query": SAML_QUERY,
        "variables": {"login": ctx.org_name, "count": 100, "after": None},
    }

    response = ctx.client.post("/graphql", json=data).json()
    org = (response.get("data") or {}).get("organization") or {}
    idp = org.get("samlIdentityProvider")
    if not idp:
        return
    yield {
        **idp,
        "org_node_id": org.get("id") or ctx.org_node_id,
        "org_name": org.get("name") or ctx.org_name,
        "org_login": ctx.org_name,
    }


@app.resource(name="external_identities", columns=ExternalIdentity, parallelized=True)
def external_identities(ctx: SourceContext):
    """Fetch external identities linked to the SAML provider.

    Args:
        saml (SamlProvider): The SAML provider to extract identities for.
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        ExternalIdentity (ExternalIdentity): External identity record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(external_identities, org_ctx)
        return

    data = {
        "query": SAML_IDENTITIES_QUERY,
        "variables": {"login": ctx.org_name, "count": 100, "after": None},
    }

    while True:
        response = ctx.client.post("/graphql", json=data).json()
        org_data = (response.get("data") or {}).get("organization") or {}
        saml_provider_data = org_data.get("samlIdentityProvider")
        if not saml_provider_data:
            return
        for identity in _graphql_nodes(saml_provider_data.get("externalIdentities")):
            yield {
                **identity,
                "saml_provider_id": saml_provider_data.get("id"),
                "saml_provider_issuer": saml_provider_data.get("issuer"),
                "saml_provider_sso_url": saml_provider_data.get("ssoUrl"),
                "org_node_id": ctx.org_node_id,
                "org_login": ctx.org_name,
            }

        page_info = (saml_provider_data.get("externalIdentities") or {}).get(
            "pageInfo"
        ) or {}
        if not page_info.get("hasNextPage"):
            return
        data["variables"]["after"] = page_info.get("endCursor")


@app.resource(name="scim_users", columns=ScimResource, parallelized=True)
def scim_users(ctx: SourceContext):
    """Fetch SCIM users for the organization.

    Args:
        ctx (SourceContext): The shared context containing the REST client and organization name.

    Yields:
        ScimResource (ScimResource): SCIM user record.
    """
    if ctx.org_contexts:
        for org_ctx in _iter_collection_contexts(ctx):
            yield from _raw_collection(scim_users, org_ctx)
        return

    scim_paginator = OffsetPaginator(
        offset_param="startIndex",
        limit_param="itemsPerPage",
        limit=100,
        total_path="totalResults",
    )
    for page in ctx.client.paginate(
        f"/scim/v2/organizations/{ctx.org_name}/Users",
        params={"startIndex": 1, "itemsPerPage": 100},
        paginator=scim_paginator,
        data_selector="Resources",
    ):
        for user in page:
            yield {**user, "org_node_id": ctx.org_node_id, "org_login": ctx.org_name}


def _org_collection_resources(ctx: SourceContext) -> tuple:
    repos_resource = repositories(ctx)
    environments_resource = repos_resource | environments(ctx)
    personal_access_tokens_resource = personal_access_tokens(ctx)
    org_resource = organizations(ctx)
    org_role_resource = org_roles(ctx)
    teams_resource = teams(ctx)
    repositories_graphql_resource = repositories_graphql(ctx)
    app_installs_resource = app_installations(ctx)
    runner_groups_resource = runner_groups(ctx)
    branch_prot_rules_resource = (
        repositories_graphql_resource | branch_protection_rules(ctx)
    )
    organization_secrets_resource = organization_secrets(ctx)
    organization_vars_resource = organization_variables(ctx)

    return (
        org_resource,
        users(ctx),
        org_role_resource,
        org_role_resource | org_role_members(ctx),
        org_role_resource | org_role_teams(ctx),
        repos_resource,
        repos_resource | repository_roles(ctx),
        repos_resource | workflows(ctx),
        repos_resource | repo_runners(ctx),
        repos_resource | repository_secrets(ctx),
        repos_resource | repository_variables(ctx),
        repos_resource | repo_role_assignments(ctx),
        environments_resource,
        environments_resource | environment_variables(ctx),
        environments_resource | environment_secrets(ctx),
        environments_resource | environment_branch_policies(ctx),
        teams_resource,
        teams_resource | team_members(ctx),
        teams_resource | team_roles(),
        runner_groups_resource,
        org_runners(ctx),
        org_runner_group_memberships(ctx),
        personal_access_tokens_resource,
        personal_access_tokens_resource | pat_repo_access(ctx),
        organization_secrets_resource,
        organization_secrets_resource | selected_organization_secrets(ctx),
        organization_vars_resource,
        organization_vars_resource | selected_organization_variables(ctx),
        personal_access_token_requests(ctx),
        scim_users(ctx),
        repositories_graphql_resource,
        repositories_graphql_resource | branches(ctx),
        branch_prot_rules_resource,
        secret_scanning_alerts(ctx),
        saml_provider(ctx),
        external_identities(ctx),
        app_installs_resource,
        app_installs_resource | applications(ctx),
    )


def _enterprise_collection_resources(
    ctx: SourceContext,
    enterprise_data: dict[str, Any],
    enterprise_orgs: list[dict[str, Any]],
    enterprise_members: list[dict[str, Any]],
    saml_provider_data: dict[str, Any] | None,
    external_identity_data: list[dict[str, Any]],
) -> tuple:
    enterprise_resource = enterprise(enterprise_data)
    enterprise_teams_resource = enterprise_teams(ctx, enterprise_data)
    enterprise_roles_resource = enterprise_roles(ctx, enterprise_data)
    enterprise_admin_roles_resource = enterprise_admin_roles(ctx, enterprise_data)
    enterprise_saml_provider_resource = enterprise_saml_provider(saml_provider_data)

    return (
        enterprise_resource,
        enterprise_organizations(enterprise_orgs),
        enterprise_users(enterprise_members),
        enterprise_managed_users(enterprise_members),
        enterprise_teams_resource,
        enterprise_teams_resource | enterprise_team_roles(),
        enterprise_teams_resource | enterprise_team_members(ctx),
        enterprise_teams_resource | enterprise_team_organizations(ctx),
        enterprise_roles_resource,
        enterprise_roles_resource | enterprise_role_users(ctx),
        enterprise_roles_resource | enterprise_role_teams(ctx),
        enterprise_admin_roles_resource,
        enterprise_admins(ctx, enterprise_data),
        enterprise_saml_provider_resource,
        enterprise_external_identities(external_identity_data),
    )


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

    if isinstance(credentials, GithubAppCredentials):
        credentials.api_uri = host

    if bool(credentials.org_name) == bool(credentials.enterprise_name):
        raise ValueError("Specify exactly one of org_name or enterprise_name.")

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

    def github_client(token: str) -> RESTClient:
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

    def app_installation_ids_by_org() -> dict[str, int]:
        if not isinstance(credentials, GithubAppCredentials):
            return {}

        installations: dict[str, int] = {}
        for installation in credentials.installations():
            if installation.get("target_type") != "Organization":
                continue
            if installation.get("suspended_at"):
                continue
            account = installation.get("account") or {}
            login = account.get("login") or account.get("slug")
            installation_id = installation.get("id")
            if login and installation_id:
                installations[login] = installation_id
        return installations

    ctx = SourceContext(
        client=github_client(credentials.header),
        org_name=credentials.org_name,
        enterprise_name=credentials.enterprise_name,
        auth_type=credentials.auth(),
    )

    if credentials.enterprise_name:
        enterprise_data, enterprise_orgs = _enterprise_profile_and_orgs(ctx)
        enterprise_members = _enterprise_member_records(ctx, enterprise_data)
        saml_provider_data, external_identity_data = _enterprise_saml_records(ctx)
        ctx.enterprise_node_id = enterprise_data["id"]

        installation_ids_by_org = app_installation_ids_by_org()
        org_contexts = []
        for org in enterprise_orgs:
            org_login = org["login"]
            org_client = ctx.client
            if isinstance(credentials, GithubAppCredentials):
                installation_id = installation_ids_by_org.get(org_login)
                if not installation_id:
                    continue
                org_client = github_client(
                    credentials.header_for_installation(installation_id)
                )

            org_contexts.append(
                OrgContext(
                    client=org_client,
                    org_name=org_login,
                    org_node_id=org["id"],
                )
            )

        ctx.org_contexts = tuple(org_contexts)

        return (
            *_enterprise_collection_resources(
                ctx,
                enterprise_data,
                enterprise_orgs,
                enterprise_members,
                saml_provider_data,
                external_identity_data,
            ),
            *_org_collection_resources(ctx),
        )

    return _org_collection_resources(ctx)
