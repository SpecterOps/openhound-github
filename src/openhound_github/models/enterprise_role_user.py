from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_helpers import enterprise_role_node_id


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.HAS_ROLE,
            description="User has enterprise role",
            traversable=True,
        ),
    ],
)
class EnterpriseRoleUser(BaseAsset):
    node_id: str
    login: str | None = None
    assignment: str | None = None
    role_id: int | str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def role_node_id(self) -> str:
        return enterprise_role_node_id(self.enterprise_node_id, self.role_id)

    @property
    def edges(self):
        if self.assignment == "direct" and self.node_id:
            yield Edge(
                kind=ek.HAS_ROLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.role_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )
