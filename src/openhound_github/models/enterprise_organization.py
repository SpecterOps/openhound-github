from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnterpriseOrganizationProperties(GHNodeProperties):
    """Properties for an enterprise-discovered organization stub.

    Attributes:
        collected: Whether this organization was collected in full.
        login: The organization login.
        environment_name: The organization environment name.
        query_enterprise: Query for the containing enterprise.
    """

    collected: bool = False
    login: str | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORGANIZATION,
        description="GitHub Organization discovered from an enterprise",
        icon="building",
        properties=GHEnterpriseOrganizationProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ORGANIZATION,
            kind=ek.CONTAINS,
            description="Enterprise contains organization",
            traversable=False,
        ),
    ],
)
class EnterpriseOrganization(BaseAsset):
    id: str
    login: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ORGANIZATION],
            properties=GHEnterpriseOrganizationProperties(
                name=self.login,
                displayname=self.login,
                node_id=self.node_id,
                environmentid=self.node_id,
                environment_name=self.login,
                login=self.login,
                collected=False,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_Organization {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._lookup.enterprise_id(), match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
