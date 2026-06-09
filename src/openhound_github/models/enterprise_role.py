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
