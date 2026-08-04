import logging
from dataclasses import dataclass

from dlt.sources.helpers.rest_client.client import RESTClient
from dlt.sources.helpers.rest_client.paginators import OffsetPaginator

from openhound_github.graphql import (
    ENTERPRISE_ADMINS_QUERY,
    ENTERPRISE_MEMBERS_QUERY,
    ENTERPRISE_SAML_PROVIDER_QUERY,
    ENTERPRISE_QUERY,
    ENTERPRISE_SAML_QUERY,
)
from openhound_github.helpers import GraphQLCursorPaginator
from openhound_github.main import app
from openhound_github.models import (
    BaseUser,
    Enterprise,
    EnterpriseAdmin,
    EnterpriseManagedUser,
    EnterpriseOrganization,
    EnterpriseRole,
    EnterpriseRoleTeam,
    EnterpriseRoleUser,
    EnterpriseTeam,
    EnterpriseTeamMember,
    EnterpriseTeamOrganization,
    EnterpriseTeamRole,
    EnterpriseUser,
    SamlProvider,
    SamlServiceProvider,
    SamlAssertionConsumerService,
    SamlIssuer,
    ExternalIdentity,
    ScimGroup,
    ScimOrganization,
    ScimUser,
)
from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
)

logger = logging.getLogger(__name__)


@dataclass
class SourceContext:
    """Shared context for GitHub API access."""

    client: RESTClient
    sso_client: RESTClient | None = None
    scim_client: RESTClient | None = None
    org_name: str | None = None
    enterprise_name: str | None = None
    collect_enterprise_scim: bool = False
    emit_legacy_scim_correlations: bool = False
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN


def iter_enterprise_scim_resources(
    client: RESTClient,
    enterprise_slug: str,
    resource_kind: str,
):
    if resource_kind not in {"Users", "Groups"}:
        raise ValueError(f"Unsupported enterprise SCIM resource: {resource_kind}")
    paginator = OffsetPaginator(
        offset_param="startIndex",
        limit_param="count",
        limit=100,
        offset=1,
        total_path="totalResults",
    )
    for page in client.paginate(
        f"/scim/v2/enterprises/{enterprise_slug}/{resource_kind}",
        params={"startIndex": 1, "count": 100},
        paginator=paginator,
        data_selector="Resources",
    ):
        yield from page


@app.resource(name="enterprise", columns=Enterprise, parallelized=True)
def enterprise(ctx: SourceContext):
    data = {
        "query": ENTERPRISE_QUERY,
        "variables": {"slug": ctx.enterprise_name, "after": None},
    }

    try:
        response = ctx.client.post("/graphql", json=data).json()
        page_enterprise = (response.get("data") or {}).get("enterprise")
        if page_enterprise:
            yield page_enterprise
    except Exception as e:
        logger.error(
            f"Error in resource 'enterprise' processing enterprise '{ctx.enterprise_name}': {e}",
            extra={"resource": "enterprise", "phase": "resource_iteration"},
        )
        return


@app.transformer(
    name="enterprise_organizations", columns=EnterpriseOrganization, parallelized=True
)
def enterprise_organizations(enterprise_data: Enterprise, ctx: SourceContext):
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

    try:
        for page_data in ctx.client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            for enterprise_object in page_data:
                es_data = enterprise_object.get("enterprise", {})
                orgs = (es_data.get("organizations") or {}).get("nodes", [])
                for org in orgs:
                    yield {
                        **org,
                        "enterprise_node_id": enterprise_data.id,
                        "enterprise_slug": ctx.enterprise_name,
                    }
    except Exception as e:
        logger.error(
            f"Error in resource 'enterprise_organizations' processing enterprise '{ctx.enterprise_name}': {e}",
            extra={"resource": "enterprise_organizations", "phase": "resource_iteration"},
        )
        return


@app.transformer(
    name="enterprise_scim_organizations",
    columns=ScimOrganization,
    parallelized=True,
)
def enterprise_scim_organizations(enterprise_data: Enterprise, ctx: SourceContext):
    yield {
        "enterprise_node_id": enterprise_data.id,
        "enterprise_slug": ctx.enterprise_name,
    }


@app.transformer(
    name="enterprise_scim_users",
    columns=ScimUser,
    parallelized=True,
)
def enterprise_scim_users(enterprise_data: Enterprise, ctx: SourceContext):
    scim_client = ctx.scim_client or ctx.client
    if not scim_client or not ctx.enterprise_name:
        raise ValueError("Enterprise SCIM collection requires a client and enterprise slug")
    for user in iter_enterprise_scim_resources(
        scim_client,
        ctx.enterprise_name,
        "Users",
    ):
        yield {
            **user,
            "enterprise_node_id": enterprise_data.id,
            "enterprise_slug": ctx.enterprise_name,
            "emit_legacy_correlation": ctx.emit_legacy_scim_correlations,
        }


@app.transformer(
    name="enterprise_scim_groups",
    columns=ScimGroup,
    parallelized=True,
)
def enterprise_scim_groups(enterprise_data: Enterprise, ctx: SourceContext):
    scim_client = ctx.scim_client or ctx.client
    if not scim_client or not ctx.enterprise_name:
        raise ValueError("Enterprise SCIM collection requires a client and enterprise slug")
    for group in iter_enterprise_scim_resources(
        scim_client,
        ctx.enterprise_name,
        "Groups",
    ):
        yield {
            **group,
            "enterprise_node_id": enterprise_data.id,
            "enterprise_slug": ctx.enterprise_name,
            "emit_legacy_correlation": ctx.emit_legacy_scim_correlations,
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
        elif base_user.id:
            yield {
                **base_user.model_dump(),
                "enterprise_slug": ctx.enterprise_name,
                "has_direct_enterprise_membership": False,
            }
        return

    if base_user.typename == "User" and base_user.id:
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

    yield {
        "id": "owners",
        "name": "owners",
        "description": "Enterprise administrators discovered from ownerInfo.admins",
        "source": "Default",
        "permissions": [],
        "enterprise_node_id": enterprise_data.id,
        "enterprise_slug": ctx.enterprise_name,
    }

    yield {
        "id": "members",
        "name": "members",
        "description": "Built-in role assigned to enterprise members",
        "source": "Default",
        "permissions": [],
        "enterprise_node_id": enterprise_data.id,
        "enterprise_slug": ctx.enterprise_name,
    }


@app.transformer(
    name="enterprise_role_teams", columns=EnterpriseRoleTeam, parallelized=True
)
def enterprise_role_teams(role: EnterpriseRole, ctx: SourceContext):
    if role.id in {"owners", "members"}:
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
    name="enterprise_role_users", columns=EnterpriseRoleUser, parallelized=True
)
def enterprise_role_users(role: EnterpriseRole, ctx: SourceContext):
    if role.id in {"owners", "members"}:
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


@app.transformer(name="enterprise_admins", columns=EnterpriseAdmin, parallelized=True)
def enterprise_admins(enterprise_data: Enterprise, ctx: SourceContext):
    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.admins.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
        allow_missing_page_info=True,
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
    name="enterprise_saml_provider",
    table_name="saml_provider",
    columns=SamlProvider,
    parallelized=True
)
def enterprise_saml_provider(enterprise_data: Enterprise, ctx: SourceContext):
    client = ctx.sso_client
    if not client:
        logger.info(
            "Skipping enterprise_saml_provider for enterprise '%s': no SSO client configured",
            ctx.enterprise_name,
        )
        return

    data = {
        "query": ENTERPRISE_SAML_PROVIDER_QUERY,
        "variables": {"slug": ctx.enterprise_name},
    }

    try:
        response = client.post("/graphql", json=data).json()
    except Exception as e:
        logger.error(
            f"Error in resource 'enterprise_saml_provider' processing enterprise '{ctx.enterprise_name}': {e}",
            extra={"resource": "enterprise_saml_provider", "phase": "resource_iteration"},
        )
        return

    enterprise_object = (response.get("data") or {}).get("enterprise", {})
    saml_provider = (enterprise_object.get("ownerInfo") or {}).get("samlIdentityProvider")
    if not saml_provider:
        logger.warning(
            "No enterprise SAML provider returned for enterprise '%s'",
            ctx.enterprise_name,
        )
        return

    yield {
        **saml_provider,
        "environment_node_id": enterprise_data.id,
        "environment_name": enterprise_data.name,
        "environment_slug": enterprise_data.slug,
        "environment_type": "enterprise",
        "github_deployment_id": ctx.github_deployment_id,
        "github_web_origin": ctx.github_web_origin,
    }

@app.transformer(
    name="enterprise_saml_service_provider",
    table_name="saml_service_provider",
    columns=SamlServiceProvider,
    parallelized=True
)
def enterprise_saml_service_provider(saml_provider: SamlProvider, ctx: SourceContext):
    yield {
        "id": saml_provider["id"],
        "issuer": saml_provider.get("issuer"),
        "environment_node_id": saml_provider["environment_node_id"],
        "environment_name": saml_provider["environment_name"],
        "environment_slug": saml_provider["environment_slug"],
        "environment_type": saml_provider["environment_type"],
        "github_deployment_id": saml_provider.get("github_deployment_id"),
        "github_web_origin": saml_provider.get("github_web_origin"),
    }

@app.transformer(
    name="enterprise_saml_assertion_consumer_service",
    table_name="saml_assertion_consumer_service",
    columns=SamlAssertionConsumerService,
    parallelized=True,
)
def enterprise_saml_assertion_consumer_service(
    saml_provider: SamlProvider, ctx: SourceContext
):
    yield {
        "environment_slug": saml_provider.get("environment_slug"),
        "environment_type": saml_provider.get("environment_type"),
        "environment_node_id": saml_provider.get("environment_node_id"),
        "environment_name": saml_provider.get("environment_name"),
        "github_deployment_id": saml_provider.get("github_deployment_id"),
        "github_web_origin": saml_provider.get("github_web_origin"),
    }

@app.transformer(
    name="enterprise_saml_issuer",
    table_name="saml_issuer",
    columns=SamlIssuer,
    parallelized=True
)
def enterprise_saml_issuer(saml_provider: SamlProvider, ctx: SourceContext):
    issuer = saml_provider.get("issuer")
    if not issuer:
        return

    yield {
        "issuer": issuer,
        "environment_slug": saml_provider.get("environment_slug"),
        "environment_type": saml_provider.get("environment_type"),
        "environment_node_id": saml_provider.get("environment_node_id"),
        "environment_name": saml_provider.get("environment_name"),
        "github_deployment_id": saml_provider.get("github_deployment_id"),
        "github_web_origin": saml_provider.get("github_web_origin"),
    }

@app.transformer(
    name="enterprise_external_identity",
    table_name="external_identities",
    columns=ExternalIdentity,
    parallelized=True,
)
def enterprise_external_identity(
    saml_provider: SamlProvider, ctx: SourceContext
):
    client = ctx.sso_client
    if not client:
        logger.info(
            "Skipping enterprise_external_identity for enterprise '%s': no SSO client configured",
            ctx.enterprise_name,
        )
        return

    paginator = GraphQLCursorPaginator(
        page_info_path="data.enterprise.ownerInfo.samlIdentityProvider.externalIdentities.pageInfo",
        cursor_variable="after",
        cursor_field="endCursor",
        has_next_field="hasNextPage",
        allow_missing_page_info=True,
    )
    data = {
        "query": ENTERPRISE_SAML_QUERY,
        "variables": {"slug": ctx.enterprise_name, "count": 100, "after": None},
    }

    try:
        for page_data in client.paginate(
            "/graphql",
            method="POST",
            json=data,
            paginator=paginator,
            data_selector="data",
        ):
            for enterprise_object in page_data:
                es_data = enterprise_object.get("enterprise", {})
                page_provider = (es_data.get("ownerInfo") or {}).get(
                    "samlIdentityProvider"
                )
                if not page_provider:
                    logger.warning(
                        "No enterprise SAML provider returned while fetching external identities for enterprise '%s'",
                        ctx.enterprise_name,
                    )
                    return
                for identity in (page_provider.get("externalIdentities") or {}).get(
                    "nodes"
                ) or []:
                    yield {
                        **identity,
                        "environment_slug": saml_provider.get("environment_slug"),
                        "github_deployment_id": saml_provider.get(
                            "github_deployment_id"
                        ),
                    }
    except Exception as e:
        logger.error(
            f"Error in resource 'enterprise_external_identity' processing enterprise '{ctx.enterprise_name}': {e}",
            extra={"resource": "enterprise_external_identity", "phase": "resource_iteration"},
        )
        return


def enterprise_resources(ctx: SourceContext):
    enterprise_resource = enterprise(ctx)
    organizations_resource = enterprise_organizations(ctx)
    members_resource = enterprise_members(ctx)
    teams_resource = enterprise_teams(ctx)
    roles_resource = enterprise_roles(ctx)
    resources = [
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
        # enterprise_resource | enterprise_admin_roles(ctx),
        enterprise_resource | enterprise_admins(ctx),
    ]

    if ctx.sso_client:
        saml_resource = enterprise_saml_provider(ctx)
        resources.extend(
            [
                enterprise_resource | saml_resource,
                enterprise_resource | saml_resource | enterprise_saml_service_provider(ctx),
                enterprise_resource | saml_resource | enterprise_saml_assertion_consumer_service(ctx),
                enterprise_resource | saml_resource | enterprise_saml_issuer(ctx),
                enterprise_resource | saml_resource | enterprise_external_identity(ctx),
            ]
        )

    if ctx.collect_enterprise_scim:
        resources.extend(
            [
                enterprise_resource | enterprise_scim_organizations(ctx),
                enterprise_resource | enterprise_scim_users(ctx),
                enterprise_resource | enterprise_scim_groups(ctx),
            ]
        )

    return tuple(resources)
