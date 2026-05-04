from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_team_node_id


@dataclass
class GHEnterpriseTeamRoleProperties(GHNodeProperties):
    """Properties for an enterprise team role.

    Attributes:
        enterpriseid: The containing enterprise node ID.
        team_name: The team display name.
        team_id: The enterprise team node ID.
        short_name: The role short name.
        type: The role type.
        environment_name: The enterprise environment name.
        query_team: Query for the team.
        query_members: Query for role members.
    """

    enterpriseid: str | None = None
    team_name: str | None = None
    team_id: str | None = None
    short_name: str | None = None
    type: str | None = None
    environment_name: str | None = None
    query_team: str | None = None
    query_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.TEAM_ROLE,
        description="GitHub Enterprise Team Role",
        icon="user-tie",
        properties=GHEnterpriseTeamRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.TEAM_ROLE,
            end=nk.ENTERPRISE_TEAM,
            kind=ek.MEMBER_OF,
            description="Enterprise team role belongs to enterprise team",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamRole(BaseAsset):
    id: int
    name: str
    slug: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def enterprise_team_node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.id)

    @property
    def node_id(self) -> str:
        return f"{self.enterprise_team_node_id}_members"

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.TEAM_ROLE, "GH_Role"],
            properties=GHEnterpriseTeamRoleProperties(
                name=f"{self.enterprise_slug}/{self.slug}/members",
                displayname="members",
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                enterpriseid=self.enterprise_node_id,
                team_name=self.name,
                team_id=self.enterprise_team_node_id,
                short_name="members",
                type="team",
                query_team=f"MATCH p=(:GH_TeamRole {{node_id:'{self.node_id}'}})-[:GH_MemberOf]->(:GH_EnterpriseTeam {{node_id:'{self.enterprise_team_node_id}'}}) RETURN p",
                query_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.MEMBER_OF,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
