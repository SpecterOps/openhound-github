from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import (
    ConditionalEdgePath,
    Edge,
    EdgePath,
    EdgeProperties,
    PropertyMatch,
)

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_team_node_id


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.ORGANIZATION,
            kind=ek.ASSIGNED_TO,
            description="Enterprise team is assigned to organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.TEAM,
            kind=ek.MEMBER_OF,
            description="Enterprise team maps to projected organization team",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamOrganization(BaseAsset):
    node_id: str
    login: str | None = None
    team_id: int
    projected_slug: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def enterprise_team_node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.team_id)

    @property
    def _assigned_to_edge(self):
        yield Edge(
            kind=ek.ASSIGNED_TO,
            start=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def member_of_team_edges(self):
        org_login = self.login or self._lookup.org_login_for_id(self.node_id)
        if org_login and self._lookup.projected_enterprise_team_exists(
            org_login, self.projected_slug
        ):
            yield Edge(
                kind=ek.MEMBER_OF,
                start=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.TEAM,
                    property_matchers=[
                        PropertyMatch(key="environmentid", value=self.node_id.upper()),
                        PropertyMatch(key="slug", value=self.projected_slug),
                    ],
                ),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def edges(self):
        yield from self._assigned_to_edge
        yield from self.member_of_team_edges
