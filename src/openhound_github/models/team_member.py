from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.TEAM_ROLE,
            kind=ek.HAS_ROLE,
            description="User has team role",
            traversable=True,
        )
    ],
)
class TeamMember(BaseAsset):
    """One record from `team_members` DLT table → one GH_HasRole edge (user → team role). No node."""

    team_id: str
    login: str
    id: str
    role: str  # "MEMBER" or "MAINTAINER"

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def team_node_id(self) -> str:
        """The ID from a GraphQL API response is the same as a regular node_id"""
        return self.team_id

    @property
    def user_node_id(self) -> str:
        """The ID from a GraphQL API response is the same as a regular node_id"""
        return self.id

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        role_type = "maintainers" if self.role == "MAINTAINER" else "members"
        role_node_id = f"{self.team_node_id}_{role_type}"
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(value=self.user_node_id, match_by="id"),
            end=EdgePath(value=role_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
