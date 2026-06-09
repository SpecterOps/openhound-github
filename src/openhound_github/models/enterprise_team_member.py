from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_team_node_id


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.TEAM_ROLE,
            kind=ek.HAS_ROLE,
            description="User has enterprise team role",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamMember(BaseAsset):
    node_id: str
    login: str | None = None
    team_id: int
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def role_node_id(self) -> str:
        return (
            f"{enterprise_team_node_id(self.enterprise_node_id, self.team_id)}_members"
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.role_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
