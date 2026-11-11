from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import (
    Edge,
    EdgePath,
    EdgeProperties,
)

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.ORGANIZATION,
            kind=ek.ASSIGNED_TO,
            description="Enterprise team is assigned to organization",
            traversable=False,
        ),
    ],
)
class EnterpriseTeamOrganization(BaseAsset):
    node_id: str
    org_database_id: int | None = None
    login: str | None = None
    team_id: int
    projected_slug: str | None = None
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def enterprise_team_node_id(self) -> str:
        return self._lookup.enterprise_team_node_id(
            self.enterprise_node_id, self.team_id
        )

    @property
    def _assigned_to_edge(self):
        yield Edge(
            kind=ek.ASSIGNED_TO,
            start=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._assigned_to_edge
