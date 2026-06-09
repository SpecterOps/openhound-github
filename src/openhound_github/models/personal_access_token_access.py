from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class Owner(BaseModel):
    login: str
    id: int
    node_id: str
    type: str
    site_admin: bool


@app.asset(
    edges=[
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN,
            end=nk.REPOSITORY,
            kind=ek.CAN_ACCESS,
            description="PAT can access repository",
            traversable=False,
        )
    ],
)
class PatRepoAccess(BaseAsset):
    """One record from `pat_repo_access` → GH_CanAccess edge (PAT → repo). No node."""

    id: int
    node_id: str
    full_name: str
    owner: Owner
    private: bool
    description: str | None = None

    # Additional
    pat_id: int
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self) -> None:
        return None

    @property
    def pat_node_id(self) -> str:
        return f"GH_PAT_{self.org_node_id}_{self.pat_id}"

    @property
    def edges(self):
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.pat_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
