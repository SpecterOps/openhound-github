from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnterpriseManagedUserProperties(GHNodeProperties):
    """Properties for a GitHub enterprise managed user wrapper.

    Attributes:
        login: The managed user login.
        full_name: The managed user display name.
        url: The managed user URL.
        created_at: When the managed user was created.
        updated_at: When the managed user was last updated.
        github_user_id: The backing GitHub user ID.
        github_username: The backing GitHub username.
        environment_name: The enterprise environment name.
        query_enterprises: Query for enterprises containing this managed user.
        query_mapped_user: Query for the backing GitHub user.
    """

    login: str | None = None
    full_name: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    github_user_id: str | None = None
    github_username: str | None = None
    environment_name: str | None = None
    query_enterprises: str | None = None
    query_mapped_user: str | None = None


class EnterpriseManagedBackingUser(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    login: str
    name: str | None = None
    email: str | None = None
    company: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_MANAGED_USER,
        description="GitHub enterprise managed user",
        icon="user-lock",
        properties=GHEnterpriseManagedUserProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_MANAGED_USER,
            kind=ek.HAS_MEMBER,
            description="Enterprise has enterprise managed user member",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_MANAGED_USER,
            end=nk.USER,
            kind=ek.MAPS_TO_USER,
            description="Enterprise managed user maps to GitHub user",
            traversable=False,
        ),
    ],
)
class EnterpriseManagedUser(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    login: str
    name: str | None = None
    url: str | None = None
    created_at: datetime | None = Field(alias="createdAt", default=None)
    updated_at: datetime | None = Field(alias="updatedAt", default=None)
    user: EnterpriseManagedBackingUser | None = None
    enterprise_node_id: str | None = None
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_MANAGED_USER],
            properties=GHEnterpriseManagedUserProperties(
                name=self.login,
                displayname=self.name or self.login,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                login=self.login,
                full_name=self.name,
                url=self.url,
                created_at=self.created_at,
                updated_at=self.updated_at,
                github_user_id=self.user.id if self.user else None,
                github_username=self.user.login if self.user else None,
                query_enterprises=f"MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_EnterpriseManagedUser {{node_id:'{self.node_id}'}}) RETURN p",
                query_mapped_user=f"MATCH p=(:GH_EnterpriseManagedUser {{node_id:'{self.node_id}'}})-[:GH_MapsToUser]->(:GH_User) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_MEMBER,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        if self.user and self.user.id:
            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
