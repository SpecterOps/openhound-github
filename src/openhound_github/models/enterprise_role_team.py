from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import (
    enterprise_role_node_id,
    enterprise_team_node_id,
)


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.HAS_ROLE,
            description="Enterprise team has enterprise role",
            traversable=True,
        ),
    ],
)
class EnterpriseRoleTeam(BaseAsset):
    id: int
    role_id: int | str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(
                value=enterprise_team_node_id(self.enterprise_node_id, self.id),
                match_by="id",
            ),
            end=EdgePath(
                value=enterprise_role_node_id(self.enterprise_node_id, self.role_id),
                match_by="id",
            ),
            properties=EdgeProperties(traversable=True),
        )
