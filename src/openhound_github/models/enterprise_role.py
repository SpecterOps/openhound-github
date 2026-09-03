from dataclasses import dataclass
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_role_node_id


ENTERPRISE_PERMISSION_EDGES: dict[str, tuple[str, bool]] = {
    "create_enterprise_organizations": (ek.CREATE_ENTERPRISE_ORGANIZATIONS, False),
    "edit_enterprise_custom_properties_for_organizations": (
        ek.EDIT_ENTERPRISE_CUSTOM_PROPERTIES_FOR_ORGANIZATIONS,
        False,
    ),
    "manage_enterprise_admins": (ek.MANAGE_ENTERPRISE_ADMINS, True),
    "manage_enterprise_identity_provider": (
        ek.MANAGE_ENTERPRISE_IDENTITY_PROVIDER,
        False,
    ),
    "manage_enterprise_members": (ek.MANAGE_ENTERPRISE_MEMBERS, True),
    "manage_enterprise_organization_admins": (
        ek.MANAGE_ENTERPRISE_ORGANIZATION_ADMINS,
        True,
    ),
    "manage_enterprise_organizations": (ek.MANAGE_ENTERPRISE_ORGANIZATIONS, False),
    "manage_enterprise_referrals": (ek.MANAGE_ENTERPRISE_REFERRALS, False),
    "manage_enterprise_teams": (ek.MANAGE_ENTERPRISE_TEAMS, False),
    "read_enterprise_audit_log": (ek.READ_ENTERPRISE_AUDIT_LOG, False),
    "read_enterprise_domain_verification": (
        ek.READ_ENTERPRISE_DOMAIN_VERIFICATION,
        False,
    ),
    "read_enterprise_members": (ek.READ_ENTERPRISE_MEMBERS, False),
    "read_enterprise_org_projects": (ek.READ_ENTERPRISE_ORG_PROJECTS, False),
    "read_enterprise_organization_admin": (
        ek.READ_ENTERPRISE_ORGANIZATION_ADMIN,
        False,
    ),
    "set_enterprise_interaction_limits": (
        ek.SET_ENTERPRISE_INTERACTION_LIMITS,
        False,
    ),
    "view_enterprise_actions_usage_metrics": (
        ek.VIEW_ENTERPRISE_ACTIONS_USAGE_METRICS,
        False,
    ),
    "view_enterprise_billing": (ek.VIEW_ENTERPRISE_BILLING, False),
    "view_enterprise_secret_scanning_alerts": (
        ek.VIEW_ENTERPRISE_SECRET_SCANNING_ALERTS,
        False,
    ),
    "write_enterprise_actions_policies": (
        ek.WRITE_ENTERPRISE_ACTIONS_POLICIES,
        False,
    ),
    "write_enterprise_billing": (ek.WRITE_ENTERPRISE_BILLING, False),
    "write_enterprise_personal_access_token_policies": (
        ek.WRITE_ENTERPRISE_PERSONAL_ACCESS_TOKEN_POLICIES,
        False,
    ),
    "write_enterprise_sso": (ek.WRITE_ENTERPRISE_SSO, False),
    "write_enterprise_team_members": (ek.WRITE_ENTERPRISE_TEAM_MEMBERS, False),
}


@dataclass
class GHEnterpriseRoleProperties(GHNodeProperties):
    """Properties for a GitHub enterprise role.

    Attributes:
        github_role_id: The raw GitHub role ID.
        short_name: The role short name.
        description: The role description.
        source: The role source.
        type: The role type.
        created_at: When the role was created.
        updated_at: When the role was last updated.
        permissions: Raw enterprise permission strings.
        environment_name: The enterprise environment name.
        query_enterprise: Query for the containing enterprise.
        query_explicit_members: Query for direct user members.
        query_team_members: Query for team-assigned members.
    """

    github_role_id: str | int | None = None
    short_name: str | None = None
    description: str | None = None
    source: str | None = None
    type: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    permissions: list[str] | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None
    query_explicit_members: str | None = None
    query_team_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_ROLE,
        description="GitHub Enterprise Role",
        icon="user-tie",
        properties=GHEnterpriseRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.CONTAINS,
            description="Enterprise contains role",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.CREATE_ENTERPRISE_ORGANIZATIONS,
            description="Enterprise role has create_enterprise_organizations capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.EDIT_ENTERPRISE_CUSTOM_PROPERTIES_FOR_ORGANIZATIONS,
            description="Enterprise role has edit_enterprise_custom_properties_for_organizations capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_ADMINS,
            description="Enterprise role has manage_enterprise_admins capability",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_IDENTITY_PROVIDER,
            description="Enterprise role has manage_enterprise_identity_provider capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_MEMBERS,
            description="Enterprise role has manage_enterprise_members capability",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_ORGANIZATION_ADMINS,
            description="Enterprise role has manage_enterprise_organization_admins capability",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_ORGANIZATIONS,
            description="Enterprise role has manage_enterprise_organizations capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_REFERRALS,
            description="Enterprise role has manage_enterprise_referrals capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.MANAGE_ENTERPRISE_TEAMS,
            description="Enterprise role has manage_enterprise_teams capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.READ_ENTERPRISE_AUDIT_LOG,
            description="Enterprise role has read_enterprise_audit_log capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.READ_ENTERPRISE_DOMAIN_VERIFICATION,
            description="Enterprise role has read_enterprise_domain_verification capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.READ_ENTERPRISE_MEMBERS,
            description="Enterprise role has read_enterprise_members capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.READ_ENTERPRISE_ORG_PROJECTS,
            description="Enterprise role has read_enterprise_org_projects capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.READ_ENTERPRISE_ORGANIZATION_ADMIN,
            description="Enterprise role has read_enterprise_organization_admin capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.SET_ENTERPRISE_INTERACTION_LIMITS,
            description="Enterprise role has set_enterprise_interaction_limits capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.VIEW_ENTERPRISE_ACTIONS_USAGE_METRICS,
            description="Enterprise role has view_enterprise_actions_usage_metrics capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.VIEW_ENTERPRISE_BILLING,
            description="Enterprise role has view_enterprise_billing capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.VIEW_ENTERPRISE_SECRET_SCANNING_ALERTS,
            description="Enterprise role has view_enterprise_secret_scanning_alerts capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.WRITE_ENTERPRISE_ACTIONS_POLICIES,
            description="Enterprise role has write_enterprise_actions_policies capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.WRITE_ENTERPRISE_BILLING,
            description="Enterprise role has write_enterprise_billing capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.WRITE_ENTERPRISE_PERSONAL_ACCESS_TOKEN_POLICIES,
            description="Enterprise role has write_enterprise_personal_access_token_policies capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.WRITE_ENTERPRISE_SSO,
            description="Enterprise role has write_enterprise_sso capability",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_ROLE,
            end=nk.ENTERPRISE,
            kind=ek.WRITE_ENTERPRISE_TEAM_MEMBERS,
            description="Enterprise role has write_enterprise_team_members capability",
            traversable=False,
        ),
    ],
)
class EnterpriseRole(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: str | int
    name: str
    description: str | None = None
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    permissions: list[str] = Field(default_factory=list)
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return enterprise_role_node_id(self.enterprise_node_id, self.id)

    @property
    def role_type(self) -> str:
        return "default" if self.source in {"Predefined", "Default"} else "custom"

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_ROLE, "GH_Role"],
            properties=GHEnterpriseRoleProperties(
                name=f"{self.enterprise_slug}/{self.name}",
                displayname=self.name,
                node_id=self.node_id,
                environmentid=self._lookup.enterprise_id(),
                environment_name=self.enterprise_slug,
                github_role_id=self.id,
                short_name=self.name,
                description=self.description,
                source=self.source,
                type=self.role_type,
                created_at=self.created_at,
                updated_at=self.updated_at,
                permissions=self.permissions,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_explicit_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_team_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole)-[:GH_MemberOf]->(:GH_EnterpriseTeam)-[:GH_HasRole]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._lookup.enterprise_id(), match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        for permission in self.permissions:
            edge_definition = ENTERPRISE_PERMISSION_EDGES.get(permission)
            if not edge_definition:
                continue
            edge_kind, traversable = edge_definition
            yield Edge(
                kind=edge_kind,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.enterprise_node_id, match_by="id"),
                properties=EdgeProperties(traversable=traversable),
            )
