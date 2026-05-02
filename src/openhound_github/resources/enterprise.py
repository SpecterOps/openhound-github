from typing import Any

from openhound_github.graphql import (
    ENTERPRISE_ADMINS_QUERY,
    ENTERPRISE_MEMBERS_QUERY,
    ENTERPRISE_QUERY,
    ENTERPRISE_SAML_QUERY,
    graphql_edges,
    graphql_nodes,
    graphql_object,
)
from openhound_github.helpers import GraphQLCursorPaginator
from openhound_github.main import app
from openhound_github.models import (
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
from openhound_github.models.enterprise import flatten_enterprise_member
from openhound_github.source_context import SourceContext


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
        enterprise_data_page = graphql_object(page_data, "enterprise")
        for edge in graphql_edges(enterprise_data_page.get("members")):
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
            for identity in graphql_nodes(saml_provider.get("externalIdentities")):
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
            enterprise_data_page = graphql_object(page_data, "enterprise")
            owner_info = enterprise_data_page.get("ownerInfo") or {}
            for edge in graphql_edges(owner_info.get("admins")):
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
