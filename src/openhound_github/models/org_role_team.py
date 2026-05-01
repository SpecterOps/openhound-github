from typing import Optional

from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@app.asset(
    edges=[
        EdgeDef(
            start=nk.TEAM,
            end=nk.ORG_ROLE,
            kind=ek.HAS_ROLE,
            description="Team has org role",
            traversable=True,
        )
    ],
)
class OrgRoleTeam(BaseAsset):
    """One record from `org_role_teams` → one GH_HasRole edge (team → role). No node."""

    id: int
    node_id: str
    url: str
    name: str
    slug: str
    description: str
    # privacy: Optional[str] = None
    permission: str
    members_url: str
    repositories_url: str
    parent: Optional[dict] = None

    # Additional
    org_role_id: int
    org_role_name: str
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def org_role_node_id(self) -> str:
        org_node_id = self.org_node_id or self._lookup.org_id()
        return f"{org_node_id}_{self.org_role_name}"

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.org_role_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
