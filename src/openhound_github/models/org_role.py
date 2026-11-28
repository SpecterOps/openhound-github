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
from openhound_github.role_ids import role_node_id
from openhound_github.models.role_permissions import role_permission_properties
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    REPOSITORY_SCOPE_TYPE,
    scope_node_id,
)
from openhound_github.models.app_management import app_management_edges

_ALL_REPO_PERMISSIONS = ("read", "triage", "write", "maintain", "admin")

_ORG_PERMISSION_EDGES: dict[str, tuple[str, bool]] = {
    "manage_organization_webhooks": ("GH_ManageOrganizationWebhooks", False),
    "org_bypass_code_scanning_dismissal_requests": (
        "GH_OrgBypassCodeScanningDismissalRequests",
        False,
    ),
    "org_bypass_secret_scanning_closure_requests": (
        "GH_OrgBypassSecretScanningClosureRequests",
        False,
    ),
    "org_review_and_manage_secret_scanning_bypass_requests": (
        "GH_OrgReviewAndManageSecretScanningBypassRequests",
        False,
    ),
    "org_review_and_manage_secret_scanning_closure_requests": (
        "GH_OrgReviewAndManageSecretScanningClosureRequests",
        False,
    ),
    "read_organization_actions_usage_metrics": (
        "GH_ReadOrganizationActionsUsageMetrics",
        False,
    ),
    "read_organization_custom_org_role": ("GH_ReadOrganizationCustomOrgRole", False),
    "read_organization_custom_repo_role": (
        "GH_ReadOrganizationCustomRepoRole",
        False,
    ),
    "resolve_secret_scanning_alerts": ("GH_ResolveSecretScanningAlerts", False),
    "view_secret_scanning_alerts": ("GH_ViewSecretScanningAlerts", False),
    "write_organization_actions_secrets": (
        "GH_WriteOrganizationActionsSecrets",
        False,
    ),
    "write_organization_actions_settings": (
        "GH_WriteOrganizationActionsSettings",
        False,
    ),
    "write_organization_actions_variables": (
        "GH_WriteOrganizationActionsVariables",
        False,
    ),
    "write_organization_custom_org_role": ("GH_WriteOrganizationCustomOrgRole", True),
    "write_organization_custom_repo_role": (
        "GH_WriteOrganizationCustomRepoRole",
        False,
    ),
    "write_organization_network_configurations": (
        "GH_WriteOrganizationNetworkConfigurations",
        False,
    ),
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
    """Organization role properties; Explore queries live in the extension schema.

    Attributes:
        github_role_id: Original role record ID before collector node-ID encoding.
        permissions_repository: Direct native permissions for repository resources.
        permissions_organization: Direct native permissions for organization resources.
        permissions_enterprise: Direct native permissions for enterprise resources.
        permissions_unclassified: Direct actions with unknown or unsupported targets.
        base_role: Immediate base role name, or null when no base is declared.
        short_name: The short display name of the role (e.g., `Owners`, `Members`, or the custom role name).
        type: `default` for built-in roles (Owner, Member) or `custom` for custom organization roles.
        source: GitHub role source, including `Predefined` for built-in API roles.
        environment_name: The name of the environment (GitHub organization).
    """

    short_name: str
    type: str
    source: str | None = None
    github_role_id: int | None = None
    base_role: str | None = None
    permissions_repository: list[str] | None = None
    permissions_organization: list[str] | None = None
    permissions_enterprise: list[str] | None = None
    permissions_unclassified: list[str] | None = None
    environment_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORG_ROLE,
        description="GitHub Organization Role",
        icon="user-tie",
        properties=GHOrgRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CAN_ACCESS,
            description="Role has access scope to its parent organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.SCOPE,
            kind=ek.CAN_ACCESS,
            description="Organization role has explicit repository permissions across its organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.APP,
            kind=ek.CAN_MANAGE_APP,
            description="Role can manage App registrations owned by its organization",
            traversable=True,
        ),
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
            kind=ek.CAN_CREATE_REPOSITORIES,
            description="Role can create repositories in the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CAN_CREATE_PUBLIC_REPOSITORIES,
            description="Role can create public repositories in the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CAN_CREATE_INTERNAL_REPOSITORIES,
            description="Role can create internal repositories in the organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORGANIZATION,
            kind=ek.CAN_CREATE_PRIVATE_REPOSITORIES,
            description="Role can create private repositories in the organization",
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
    name: str  # role-only name from the API, e.g. "owners" or "Custom Role Manager"
    created_at: datetime
    updated_at: datetime | None = None
    organization: Organization | None = None
    base_role: str | None = None
    permissions: list[str] = Field(
        default_factory=list
    )  # fine-grained strings for custom roles

    # Additional
    type: str
    source: str | None = None
    org_node_id: str
    org_login: str

    @property
    def node_id(self) -> str:
        builtin = self.type == "default" and self.source in {None, "Default"}
        return role_node_id(
            "organization",
            self._lookup.role_parent_database_id("organization", self.org_node_id),
            self.name if builtin else self.id,
            builtin=builtin,
        )

    @property
    def as_node(self) -> GHNode:
        qualified_name = f"{self.org_login}/{self.name}"
        return GHNode(
            kinds=[nk.ORG_ROLE, "GH_Role"],
            properties=GHOrgRoleProperties(
                name=qualified_name,
                displayname=qualified_name,
                node_id=self.node_id,
                short_name=self.name,
                github_role_id=self.id,
                base_role=self.base_role if self.base_role != "none" else None,
                **self._permission_properties,
                type=self.type,
                source=self.source,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
            ),
        )

    @property
    def _permission_properties(self):
        return role_permission_properties(
            self.name,
            "Organization",
            self.permissions if "permissions" in self.model_fields_set else None,
            synthesized=self.type == "default" and self.source in {None, "Default"},
        )

    @property
    def _repository_scope_edges(self):
        direct = self._permission_properties["permissions_repository"]
        if not direct:
            return
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(
                value=scope_node_id(
                    self.org_node_id, REPOSITORY_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE
                ),
                match_by="id",
            ),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _can_create_repos_edge(self):
        if self.type == "default" and (self.name == "owners" or self.name == "members"):
            creation_flags = self._lookup.members_can_create_repository(
                self.org_login
            ) or (False, False, False, False)
            (
                can_create_repositories,
                can_create_public_repositories,
                can_create_internal_repositories,
                can_create_private_repositories,
            ) = creation_flags

            if self.name == "owners":
                can_create_repositories = True
                can_create_public_repositories = True
                can_create_private_repositories = True

            if can_create_private_repositories:
                yield Edge(
                    kind=ek.CAN_CREATE_PRIVATE_REPOSITORIES,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.org_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

            if can_create_public_repositories:
                yield Edge(
                    kind=ek.CAN_CREATE_PUBLIC_REPOSITORIES,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.org_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

            if can_create_internal_repositories:
                yield Edge(
                    kind=ek.CAN_CREATE_INTERNAL_REPOSITORIES,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.org_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

            if can_create_repositories:
                yield Edge(
                    kind=ek.CAN_CREATE_REPOSITORIES,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.org_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

    @property
    def _owners_edge(self):
        if self.type == "default" and self.name == "owners":
            base_node_id = self._lookup.org_role_node_id(self.org_node_id, "all_repo_admin")
            if base_node_id:
                yield Edge(
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=base_node_id, match_by="id"),
                    kind=ek.HAS_BASE_ROLE,
                    properties=EdgeProperties(traversable=True),
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
                kind=ek.CREATE_TEAM,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.org_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
            if self.base_role and self.base_role != "none":
                base_node_id = self._lookup.org_role_node_id(
                    self.org_node_id, f"all_repo_{self.base_role}"
                )
                if base_node_id:
                    yield Edge(
                        kind=ek.HAS_BASE_ROLE,
                        start=EdgePath(value=self.node_id, match_by="id"),
                        end=EdgePath(
                            value=base_node_id,
                            match_by="id",
                        ),
                        properties=EdgeProperties(traversable=True),
                    )

    @property
    def _custom_edges(self):
        if self.type == "custom":
            if self.base_role and self.base_role in _ALL_REPO_PERMISSIONS:
                base_node_id = self._lookup.org_role_node_id(
                    self.org_node_id, f"all_repo_{self.base_role}"
                )
                if base_node_id:
                    yield Edge(
                        kind=ek.HAS_BASE_ROLE,
                        start=EdgePath(value=self.node_id, match_by="id"),
                        end=EdgePath(
                            value=base_node_id,
                            match_by="id",
                        ),
                        properties=EdgeProperties(traversable=True),
                    )
            for perm in self.permissions:
                edge_definition = _ORG_PERMISSION_EDGES.get(perm)
                if edge_definition:
                    edge_kind, traversable = edge_definition
                    yield Edge(
                        kind=edge_kind,
                        start=EdgePath(value=self.node_id, match_by="id"),
                        end=EdgePath(value=self.org_node_id, match_by="id"),
                        properties=EdgeProperties(traversable=traversable),
                    )

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._contains_edge
        yield from self._repository_scope_edges
        yield from self._owners_edge
        yield from self._members_edge
        yield from self._can_create_repos_edge
        yield from self._custom_edges
        is_predefined = self.source == "Predefined" or (
            self.type == "default" and self.source in {None, "Default"}
        )
        if is_predefined and self.name in {"owners", "app_manager"}:
            yield from app_management_edges(
                self._lookup,
                role_node_id=self.node_id,
                role_name=self.name,
                is_predefined=is_predefined,
                account_node_id=self.org_node_id,
                account_type="Organization",
            )
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.org_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
