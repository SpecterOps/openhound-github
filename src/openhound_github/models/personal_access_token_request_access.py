from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.pat_ids import pat_request_node_id


@app.asset(
    edges=[
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            end=nk.REPOSITORY,
            kind=ek.CAN_ACCESS,
            description="Pending PAT request targets repository access",
            traversable=False,
        )
    ]
)
class PatRequestRepoAccess(BaseAsset):
    node_id: str
    request_id: int
    org_login: str

    @property
    def as_node(self):
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(
                value=pat_request_node_id(
                    self._lookup.org_database_id_for_login(self.org_login),
                    self.request_id,
                ),
                match_by="id",
            ),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
