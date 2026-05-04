from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnterpriseUserProperties(GHNodeProperties):
    """Properties for a GitHub enterprise member user.

    Attributes:
        collected: Whether this user was collected directly.
        login: The GitHub login.
        full_name: The user's display name.
        company: The user's company.
        email: The user's public email.
        environment_name: The enterprise environment name.
        query_enterprises: Query for enterprise memberships.
    """

    collected: bool = True
    login: str | None = None
    full_name: str | None = None
    company: str | None = None
    email: str | None = None
    environment_name: str | None = None
    query_enterprises: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.USER,
        description="GitHub enterprise member user",
        icon="user",
        properties=GHEnterpriseUserProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.USER,
            kind=ek.HAS_MEMBER,
            description="Enterprise has user member",
            traversable=False,
        ),
    ],
)
class EnterpriseUser(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    login: str
    name: str | None = None
    email: str | None = None
    company: str | None = None
    enterprise_node_id: str | None = None
    enterprise_slug: str
    has_direct_enterprise_membership: bool = True

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.USER],
            properties=GHEnterpriseUserProperties(
                name=self.login,
                displayname=self.name or self.login,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                login=self.login,
                full_name=self.name,
                company=self.company,
                email=self.email,
                query_enterprises=f"MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_User {{node_id:'{self.node_id}'}}) RETURN p UNION MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_EnterpriseManagedUser)-[:GH_MapsToUser]->(:GH_User {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        if self.has_direct_enterprise_membership:
            yield Edge(
                kind=ek.HAS_MEMBER,
                start=EdgePath(value=self.enterprise_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
