from dataclasses import dataclass

from dlt.sources.helpers.rest_client.client import RESTClient

from openhound_github.graphql import (
    ENTERPRISE_ADMINS_QUERY,
    ENTERPRISE_MEMBERS_QUERY,
    ENTERPRISE_QUERY,
    ENTERPRISE_SAML_QUERY,
)
from openhound_github.helpers import GraphQLCursorPaginator
from openhound_github.main import app
from openhound_github.models import (
    BaseUser,
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
)


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    org_name: str | None = None
    enterprise_name: str | None = None


@app.resource(name="enterprise", columns=Enterprise, parallelized=True)
def enterprise(ctx: SourceContext):

    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.organizations.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_QUERY,
        "variables": {"slug": ctx.enterprise_name, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        page_enterprise = page_data[0].get("enterprise")

        if page_enterprise:
            yield page_enterprise


@app.transformer(
    name="enterprise_organizations", columns=EnterpriseOrganization, parallelized=True
)
def enterprise_organizations(enterprise_data: Enterprise, ctx: SourceContext):
    orgs = enterprise_data.organizations.get("nodes", [])
    for org in orgs:
        yield {
            **org,
            "enterprise_node_id": enterprise_data.id,
            "enterprise_slug": ctx.enterprise_name,
        }


@app.transformer(name="enterprise_members", columns=BaseUser, parallelized=True)
def enterprise_members(enterprise_data: Enterprise, ctx: SourceContext):

    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.members.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_MEMBERS_QUERY,
        "variables": {"slug": ctx.enterprise_name, "count": 100, "after": None},
    }
    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        for enterprise_object in page_data:
            es_data = enterprise_object.get("enterprise", {})
            members = es_data.get("members", {})
            for edge in members.get("edges", []):
                node = edge.get("node")
                if node:
                    yield {
                        **node,
                        "enterprise_node_id": enterprise_data.id,
                        "enterprise_slug": ctx.enterprise_name,
                    }


@app.transformer(name="enterprise_users", columns=EnterpriseUser, parallelized=True)
def enterprise_users(base_user: BaseUser, ctx: SourceContext):
    if base_user.typename == "EnterpriseUserAccount":
        if base_user.user and base_user.user.id:
            yield {
                **base_user.user.model_dump(),
                "enterprise_slug": ctx.enterprise_name,
                "has_direct_enterprise_membership": False,
            }

    if base_user.id:
        yield {
            **base_user.model_dump(),
            "enterprise_slug": ctx.enterprise_name,
            "has_direct_enterprise_membership": True,
        }


@app.transformer(
    name="enterprise_managed_users", columns=EnterpriseManagedUser, parallelized=True
)
def enterprise_managed_users(base_user: BaseUser, ctx: SourceContext):
    if base_user.typename == "EnterpriseUserAccount":
        yield {
            **base_user.model_dump(),
            "enterprise_slug": ctx.enterprise_name,
        }


@app.transformer(name="enterprise_teams", columns=EnterpriseTeam, parallelized=True)
def enterprise_teams(enterprise_data: Enterprise, ctx: SourceContext):

    for page in ctx.client.paginate(
        f"/enterprises/{ctx.enterprise_name}/teams", params={"per_page": 100}
    ):
        for team in page:
            yield {
                **team,
                "enterprise_node_id": enterprise_data.id,
                "enterprise_slug": ctx.enterprise_name,
            }


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

    for page in ctx.client.paginate(
        f"/enterprises/{ctx.enterprise_name}/teams/{team.id}/memberships",
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


@app.transformer(
    name="enterprise_team_organizations",
    columns=EnterpriseTeamOrganization,
    parallelized=True,
)
def enterprise_team_organizations(team: EnterpriseTeam, ctx: SourceContext):

    for page in ctx.client.paginate(
        f"/enterprises/{ctx.enterprise_name}/teams/{team.id}/organizations",
        params={"per_page": 100},
    ):
        for org in page:
            node_id = org.get("node_id") or org.get("id")
            print(org)
            if node_id:
                yield {
                    **org,
                    "node_id": node_id,
                    "team_id": team.id,
                    "projected_slug": team.slug,
                    "enterprise_node_id": team.enterprise_node_id,
                    "enterprise_slug": team.enterprise_slug,
                }


@app.transformer(name="enterprise_roles", columns=EnterpriseRole, parallelized=True)
def enterprise_roles(enterprise_data: Enterprise, ctx: SourceContext):
    result = ctx.client.get(
        f"/enterprises/{ctx.enterprise_name}/enterprise-roles"
    ).json()

    for role in result.get("roles", []):
        yield {
            **role,
            "enterprise_node_id": enterprise_data.id,
            "enterprise_slug": ctx.enterprise_name,
        }


@app.transformer(
    name="enterprise_admin_roles", columns=EnterpriseRole, parallelized=True
)
def enterprise_admin_roles(enterprise_data: Enterprise, ctx: SourceContext):
    yield {
        "id": "owners",
        "name": "owners",
        "description": "Enterprise administrators discovered from ownerInfo.admins",
        "source": "Default",
        "permissions": [],
        "enterprise_node_id": enterprise_data.id,
        "enterprise_slug": ctx.enterprise_name,
    }


@app.transformer(
    name="enterprise_role_users", columns=EnterpriseRoleUser, parallelized=True
)
def enterprise_role_users(role: EnterpriseRole, ctx: SourceContext):
    if role.id == "owners":
        return

    for page in ctx.client.paginate(
        f"/enterprises/{ctx.enterprise_name}/enterprise-roles/{role.id}/users",
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


@app.transformer(
    name="enterprise_role_teams", columns=EnterpriseRoleTeam, parallelized=True
)
def enterprise_role_teams(role: EnterpriseRole, ctx: SourceContext):
    if role.id == "owners":
        return

    for page in ctx.client.paginate(
        f"/enterprises/{ctx.enterprise_name}/enterprise-roles/{role.id}/teams",
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


@app.transformer(
    name="enterprise_admins", columns=EnterpriseRoleUser, parallelized=True
)
def enterprise_admins(enterprise_data: Enterprise, ctx: SourceContext):
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.admins.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_ADMINS_QUERY,
        "variables": {"slug": ctx.enterprise_name, "count": 100, "after": None},
    }
    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        for enterprise_object in page_data:
            es_data = enterprise_object.get("enterprise", {})
            owner_info = es_data.get("ownerInfo") or {}
            for edge in (owner_info.get("admins") or {}).get("edges") or []:
                node = edge.get("node")
                if node and node.get("id"):
                    yield {
                        "node_id": node["id"],
                        "login": node.get("login"),
                        "assignment": "direct",
                        "role_id": "owners",
                        "enterprise_node_id": enterprise_data.id,
                        "enterprise_slug": ctx.enterprise_name,
                    }


@app.transformer(
    name="enterprise_saml_provider", columns=EnterpriseSamlProvider, parallelized=True
)
def enterprise_saml_provider(enterprise_data: Enterprise, ctx: SourceContext):
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.samlIdentityProvider.externalIdentities.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_SAML_QUERY,
        "variables": {"slug": ctx.enterprise_name, "count": 1, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        for enterprise_object in page_data:
            es_data = enterprise_object.get("enterprise", {})
            saml_provider = (es_data.get("ownerInfo") or {}).get("samlIdentityProvider")
            if not saml_provider:
                return
            yield {
                **{k: v for k, v in saml_provider.items() if k != "externalIdentities"},
                "enterprise_node_id": enterprise_data.id,
                "enterprise_slug": ctx.enterprise_name,
            }


@app.transformer(
    name="enterprise_external_identities",
    columns=EnterpriseExternalIdentity,
    parallelized=True,
)
def enterprise_external_identities(
    saml_provider: EnterpriseSamlProvider, ctx: SourceContext
):

    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.samlIdentityProvider.externalIdentities.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
    )
    data = {
        "query": ENTERPRISE_SAML_QUERY,
        "variables": {"slug": ctx.enterprise_name, "count": 100, "after": None},
    }

    for page_data in ctx.client.paginate(
        "/graphql",
        method="POST",
        json=data,
        paginator=paginator,
        data_selector="data",
    ):
        for enterprise_object in page_data:
            es_data = enterprise_object.get("enterprise", {})
            page_provider = (es_data.get("ownerInfo") or {}).get("samlIdentityProvider")
            if not page_provider:
                return
            for identity in (page_provider.get("externalIdentities") or {}).get(
                "nodes"
            ) or []:
                yield {
                    **identity,
                    "saml_provider_id": saml_provider.id,
                    "saml_provider_issuer": saml_provider.issuer,
                    "saml_provider_sso_url": saml_provider.sso_url,
                    "enterprise_node_id": saml_provider.enterprise_node_id,
                    "enterprise_slug": saml_provider.enterprise_slug,
                }


def enterprise_resources(ctx: SourceContext):
    enterprise_resource = enterprise(ctx)
    organizations_resource = enterprise_organizations(ctx)
    members_resource = enterprise_members(ctx)
    teams_resource = enterprise_teams(ctx)
    roles_resource = enterprise_roles(ctx)
    saml_resource = enterprise_saml_provider(ctx)
    return (
        enterprise_resource,
        enterprise_resource | organizations_resource,
        enterprise_resource | members_resource | enterprise_users(ctx),
        enterprise_resource | members_resource | enterprise_managed_users(ctx),
        enterprise_resource | teams_resource,
        enterprise_resource | teams_resource | enterprise_team_roles,
        enterprise_resource | teams_resource | enterprise_team_members(ctx),
        enterprise_resource | teams_resource | enterprise_team_organizations(ctx),
        enterprise_resource | roles_resource,
        enterprise_resource | roles_resource | enterprise_role_users(ctx),
        enterprise_resource | roles_resource | enterprise_role_teams(ctx),
        enterprise_resource | enterprise_admin_roles(ctx),
        enterprise_resource | enterprise_admins(ctx),
        enterprise_resource | saml_resource,
        enterprise_resource | saml_resource | enterprise_external_identities(ctx),
    )
