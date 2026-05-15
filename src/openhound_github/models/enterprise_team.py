from dataclasses import dataclass
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_team_node_id


@dataclass
class GHEnterpriseTeamProperties(GHNodeProperties):
    """Properties for a GitHub enterprise team.

    Attributes:
        github_team_id: The raw GitHub enterprise team ID.
        slug: The enterprise team slug.
        projected_slug: The organization-projected team slug.
        group_id: The linked SCIM group ID.
        description: The team description.
        created_at: When the team was created.
        updated_at: When the team was last updated.
        environment_name: The enterprise environment name.
        query_enterprise: Query for the containing enterprise.
        query_assigned_organizations: Query for assigned organizations.
        query_projected_teams: Query for projected organization teams.
        query_members: Query for team members.
    """

    github_team_id: str | int | None = None
    slug: str | None = None
    projected_slug: str | None = None
    group_id: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None
    query_assigned_organizations: str | None = None
    query_projected_teams: str | None = None
    query_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_TEAM,
        description="GitHub Enterprise Team",
        icon="users-between-lines",
        properties=GHEnterpriseTeamProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_TEAM,
            kind=ek.CONTAINS,
            description="Enterprise contains team",
            traversable=False,
        ),
    ],
)
class EnterpriseTeam(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    name: str
    slug: str
    group_id: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_TEAM],
            properties=GHEnterpriseTeamProperties(
                name=self.name,
                displayname=self.name,
                node_id=self.node_id,
                environmentid=self._lookup.enterprise_id(),
                environment_name=self.enterprise_slug,
                github_team_id=self.id,
                slug=self.slug,
                projected_slug=self.slug,
                group_id=self.group_id,
                description=self.description,
                created_at=self.created_at,
                updated_at=self.updated_at,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}}) RETURN p",
                query_assigned_organizations=f"MATCH p=(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}})-[:GH_AssignedTo]->(:GH_Organization) RETURN p",
                query_projected_teams=f"MATCH p=(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}})-[:GH_MemberOf]->(:GH_Team) RETURN p",
                query_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole)-[:GH_MemberOf]->(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}}) RETURN p",
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
