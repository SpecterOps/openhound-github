from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHTeamRoleProperties(GHNodeProperties):
    """Team role properties and accordion panel queries.
    
    Attributes:
        short_name: The short role name: `member` or `maintainer`.
        type: Always `default` for team roles.
        team_name: The team name property.
        team_id: The team id property.
        environment_name: The name of the environment (GitHub organization).
        query_team: Query for team.
        query_members: Query for members.
        query_repositories: Query for repositories.
    """

    short_name: str | None = None
    type: str | None = None
    team_name: str | None = None
    team_id: str | None = None
    environment_name: str | None = None
    query_team: str | None = None
    query_members: str | None = None
    query_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.TEAM_ROLE,
        description="GitHub Team Role (members or maintainers)",
        icon="user-tie",
        properties=GHTeamRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.TEAM_ROLE,
            end=nk.TEAM,
            kind=ek.MEMBER_OF,
            description="Team role belongs to team",
            traversable=True,
        ),
        EdgeDef(
            start=nk.TEAM_ROLE,
            end=nk.TEAM,
            kind=ek.ADD_MEMBER,
            description="Maintainers role can add members to team",
            traversable=False,
        ),
    ],
)
class TeamRole(BaseAsset):
    """One record from `team_roles` DLT table → one GH_TeamRole node + membership edges to the team."""

    type: str
    team_node_id: str
    team_name: str
    team_slug: str

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self):
        return f"{self.team_node_id}_{self.type}"

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=["GH_TeamRole", "GH_Role"],
            properties=GHTeamRoleProperties(
                name=f"{self.org_login}/{self.team_slug}/{self.type}",
                displayname=self.type,
                node_id=rid,
                short_name=self.type,
                type="team",
                team_name=self.team_name,
                team_id=self.team_node_id,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_team=f"MATCH p=(:GH_TeamRole {{node_id:'{rid}'}})-[:GH_MemberOf]->(:GH_Team) RETURN p",
                query_members=f"MATCH p=(:GH_User)-[GH_HasRole]->(:GH_TeamRole {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_TeamRole {{node_id:'{rid}'}})-[:GH_MemberOf]->(:GH_Team)-[:GH_HasRole|GH_HasBaseRole*1..]->(:GH_RepoRole)-[]->(:GH_Repository) RETURN p",
            ),
        )

    @property
    def _maintainers_edge(self):
        if self.type == "maintainers":
            yield Edge(
                kind=ek.ADD_MEMBER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.team_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield Edge(
            kind=ek.MEMBER_OF,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.team_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )

        yield from self._maintainers_edge
