from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

_ALL_REPO_PERMISSIONS = ("read", "triage", "write", "maintain", "admin")

_ORG_PERMISSION_EDGES: dict[str, str] = {
    "manage_organization_webhooks": "GH_ManageOrganizationWebhooks",
    "org_bypass_code_scanning_dismissal_requests": "GH_OrgBypassCodeScanningDismissalRequests",
    "org_bypass_secret_scanning_closure_requests": "GH_OrgBypassSecretScanningClosureRequests",
    "org_review_and_manage_secret_scanning_bypass_requests": "GH_OrgReviewAndManageSecretScanningBypassRequests",
    "org_review_and_manage_secret_scanning_closure_requests": "GH_OrgReviewAndManageSecretScanningClosureRequests",
    "read_organization_actions_usage_metrics": "GH_ReadOrganizationActionsUsageMetrics",
    "read_organization_custom_org_role": "GH_ReadOrganizationCustomOrgRole",
    "read_organization_custom_repo_role": "GH_ReadOrganizationCustomRepoRole",
    "resolve_secret_scanning_alerts": "GH_ResolveSecretScanningAlerts",
    "view_secret_scanning_alerts": "GH_ViewSecretScanningAlerts",
    "write_organization_actions_secrets": "GH_WriteOrganizationActionsSecrets",
    "write_organization_actions_settings": "GH_WriteOrganizationActionsSettings",
    "write_organization_actions_variables": "GH_WriteOrganizationActionsVariables",
    "write_organization_custom_org_role": "GH_WriteOrganizationCustomOrgRole",
    "write_organization_custom_repo_role": "GH_WriteOrganizationCustomRepoRole",
    "write_organization_network_configurations": "GH_WriteOrganizationNetworkConfigurations",
}


class Organization(BaseModel):
    """One record from the `organizations` DLT table → one GH_Organization node."""

    id: int
    node_id: str
    login: str
    name: str | None = None
    description: str | None = None


@dataclass
class GHOrgRoleProperties(GHNodeProperties):
    """Org role properties and accordion panel queries.
    
    Attributes:
        short_name: The short display name of the role (e.g., `Owners`, `Members`, or the custom role name).
        type: `default` for built-in roles (Owner, Member) or `custom` for custom organization roles.
        environment_name: The name of the environment (GitHub organization).
        query_explicit_members: Query for explicit members.
        query_unrolled_members: Query for unrolled members.
        query_org_permissions: Query for org permissions.
        query_repo_permissions: Query for repo permissions.
    """

    short_name: str
    type: str
    environment_name: str | None = None
    query_explicit_members: str | None = None
    query_unrolled_members: str | None = None
    query_org_permissions: str | None = None
    query_repo_permissions: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORG_ROLE,
        description="GitHub Organization Role",
        icon="user-tie",
        properties=GHOrgRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.ORG_ROLE,
            kind=ek.CONTAINS,
            description="Org contains role",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORG_ROLE,
            kind=ek.HAS_BASE_ROLE,
            description="Role inherits base role",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CREATE_REPOSITORY,
            description="Role can create repositories in the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.INVITE_MEMBER,
            description="Role can invite members to the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.ADD_COLLABORATOR,
            description="Role can add outside collaborators to repositories",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CREATE_TEAM,
            description="Role can create teams in the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.TRANSFER_REPOSITORY,
            description="Role can transfer repositories out of the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.VIEW_SECRET_SCANNING_ALERTS,
            description="Role can view secret scanning alerts for the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.RESOLVE_SECRET_SCANNING_ALERTS,
            description="Role can resolve secret scanning alerts for the organization",
            traversable=False,
        ),
    ],
)
class OrgRole(BaseAsset):
    """One record from the `org_roles` DLT table → one GH_OrgRole node + edges."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    # node_id: int = Field(alias="id")
    id: int
    name: str  # full: "my-org/owners"
    created_at: datetime
    updated_at: datetime | None = None
    organization: Organization | None = None
    base_role: str | None = None
    permissions: list[str] = Field(
        default_factory=list
    )  # fine-grained strings for custom roles

    # Additional
    type: str
    org_node_id: str
    org_login: str

    @property
    def node_id(self) -> str:
        return f"{self.org_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ORG_ROLE, "GH_Role"],
            properties=GHOrgRoleProperties(
                name=self.name,
                displayname=f"{self.org_login}/{self.name}",
                node_id=self.node_id,
                short_name=self.name,
                type="custom",
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_explicit_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_OrgRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_unrolled_members=f"MATCH p=(:GH_User)-[:GH_HasRole|GH_HasBaseRole|GH_MemberOf*1..]->(:GH_OrgRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_org_permissions=f"MATCH p=(:GH_OrgRole {{node_id:'{self.node_id}'}})-[]->(:GH_Organization) RETURN p",
                query_repo_permissions=f"MATCH p=(s:GH_OrgRole {{node_id:'{self.node_id}'}})-[:GH_HasBaseRole]->(d:GH_OrgRole) WHERE s<>d RETURN p",
            ),
        )

    @property
    def _owners_edge(self):
        if self.type == "default" and self.name == "owners":
            yield Edge(
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=f"{self.org_node_id}_all_repo_admin", match_by="id"),
                kind=ek.HAS_BASE_ROLE,
                properties=EdgeProperties(traversable=True),
            )

            yield Edge(
                kind=ek.CREATE_REPOSITORY,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

            yield Edge(
                kind=ek.INVITE_MEMBER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.ADD_COLLABORATOR,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.CREATE_TEAM,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.TRANSFER_REPOSITORY,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.VIEW_SECRET_SCANNING_ALERTS,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _members_edge(self):
        if self.type == "default" and self.name == "members":
            yield Edge(
                kind=ek.CREATE_REPOSITORY,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.CREATE_TEAM,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            if self.base_role and self.base_role != "none":
                yield Edge(
                    kind=ek.HAS_BASE_ROLE,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(
                        value=f"{self.org_node_id}_all_repo_{self.base_role}",
                        match_by="id",
                    ),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _custom_edges(self):

        if self.type == "custom":
            if self.base_role and self.base_role in _ALL_REPO_PERMISSIONS:
                yield Edge(
                    kind=ek.HAS_BASE_ROLE,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(
                        value=f"{self.org_node_id}_all_repo_{self.base_role}",
                        match_by="id",
                    ),
                    properties=EdgeProperties(traversable=True),
                )
            for perm in self.permissions:
                edge_kind = _ORG_PERMISSION_EDGES.get(perm)
                if edge_kind:
                    yield Edge(
                        kind=edge_kind,
                        start=EdgePath(value=self.node_id, match_by="id"),
                        end=EdgePath(value=self.org_node_id, match_by="id"),
                        properties=EdgeProperties(traversable=False),
                    )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

        yield from self._owners_edge
        yield from self._members_edge
        yield from self._custom_edges
