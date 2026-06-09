from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.ORG_ROLE,
            kind=ek.HAS_ROLE,
            description="User has org role",
            traversable=True,
        )
    ],
)
class OrgRoleMember(BaseAsset):
    """One record from `org_role_members` → one GH_HasRole edge (user → role). No node."""

    # org_role_node_id: str
    # user_node_id: str
    # user_login: str

    id: int
    node_id: str

    login: str
    name: str | None = None
    type: str
    site_admin: bool

    # Additional
    org_role_id: int
    org_role_name: str
    org_node_id: str
    org_login: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def org_role_node_id(self) -> str:
        return f"{self.org_node_id}_{self.org_role_name}"

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.org_role_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
