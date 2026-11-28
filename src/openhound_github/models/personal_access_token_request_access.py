from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.pat_ids import collected_pat_node_id


@dataclass
class RequestRepositoryAccessProperties(EdgeProperties):
    repository_listing_complete: bool | None = None


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
    repository_listing_complete: bool | None = None

    @property
    def as_node(self):
        return None

    @property
    def edges(self):
        request_node_id = collected_pat_node_id(
            self._lookup.org_database_id_for_login(self.org_login),
            self.request_id,
            org_login=self.org_login,
            resource="pat_request_repo_access",
            request=True,
        )
        if request_node_id is None:
            return
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(
                value=request_node_id,
                match_by="id",
            ),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=RequestRepositoryAccessProperties(
                traversable=False,
                repository_listing_complete=self.repository_listing_complete,
            ),
        )
