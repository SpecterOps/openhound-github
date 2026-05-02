from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class Permissions(BaseModel):
    organization: dict | None = None
    repository: dict | None = None


class Owner(BaseModel):
    login: str
    id: int
    type: str
    node_id: str


@dataclass
class GHPersonalAccessTokenProperties(GHNodeProperties):
    """PAT properties and accordion panel queries.

    Attributes:
        environment_name: The name of the environment (GitHub organization) where the token has access.
        owner_id: The GitHub ID of the token owner.
        owner_node_id: The GraphQL node ID of the token owner.
        token_expires_at: The ISO 8601 timestamp of when the token expires.
        token_last_used_at: The ISO 8601 timestamp of when the token was last used.
        access_granted_at: The ISO 8601 timestamp of when the token was granted to the organization. |
        token_name: The user-assigned display name of the token.
        owner_login: The login handle of the user who owns the token.
        repository_selection: Whether the token has access to `all`, `subset`, or `none` of the organization's repositories.
        token_expired: Whether the token has expired.
        query_organization_permissions: OpenGraph query for related organization permissions.
        query_user: OpenGraph query for related user.
        query_repositories: OpenGraph query for related repositories.
    """

    environment_name: str
    owner_id: str | None = None
    # TODO: owner_node_id?
    owner_node_id: str | None = None
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    # TODO: permissions:
    access_granted_at: datetime | None = None
    token_name: str | None = None
    owner_login: str | None = None
    repository_selection: str | None = None
    token_expired: bool | None = None
    query_organization_permissions: str | None = None
    query_user: str | None = None
    query_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.PERSONAL_ACCESS_TOKEN,
        description="GitHub Fine-Grained Personal Access Token",
        icon="key",
        properties=GHPersonalAccessTokenProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.PERSONAL_ACCESS_TOKEN,
            kind=ek.HAS_PERSONAL_ACCESS_TOKEN,
            description="User owns PAT",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.PERSONAL_ACCESS_TOKEN,
            kind=ek.CONTAINS,
            description="Org contains PAT",
            traversable=False,
        ),
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN,
            end=nk.ORGANIZATION,
            kind=ek.CAN_ACCESS,
            description="PAT can access org",
            traversable=False,
        ),
    ],
)
class PersonalAccessToken(BaseAsset):
    """One record from `personal_access_tokens` → one GH_PersonalAccessToken node + edges."""

    id: int
    owner: Owner
    repository_selection: str | None = None
    repositories_url: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    permissions: Permissions
    token_id: int
    token_name: str
    token_expired: bool
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def _org_node_id(self) -> str:
        return self.org_node_id or self._lookup.org_id()

    @property
    def _org_login(self) -> str:
        return self.org_login or self._lookup.org_login()

    @property
    def node_id(self) -> str:
        """Construct a synthetic node_id for this PAT based on org node ID and token ID. This is needed to link users to their PATs via edges, since GH doesn't return unique IDs for PATs."""
        org_node_id = self._org_node_id
        return f"GH_PAT_{org_node_id}_{self.id}"

    @property
    def as_node(self) -> GHNode:
        pid = self.node_id
        return GHNode(
            kinds=[nk.PERSONAL_ACCESS_TOKEN],
            properties=GHPersonalAccessTokenProperties(
                name=self.token_name,
                displayname=self.token_name,
                node_id=pid,
                token_name=self.token_name,
                owner_login=self.owner.login,
                repository_selection=self.repository_selection,
                token_expired=self.token_expired,
                environmentid=self._org_node_id,
                environment_name=self._org_login,
                token_expires_at=self.token_expires_at,
                owner_id=self.owner.id if self.owner else None,
                token_last_used_at=self.token_last_used_at,
                query_organization_permissions=f"MATCH p=(:GH_PersonalAccessToken {{node_id:'{pid}'}})-[:GH_CanAccess]->(:GH_Organization) RETURN p",
                query_user=f"MATCH p=(:GH_User)-[:GH_HasPersonalAccessToken]->(:GH_PersonalAccessToken {{node_id:'{pid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_PersonalAccessToken {{node_id:'{pid}'}})-[:GH_CanAccess]->(:GH_Repository) RETURN p LIMIT 1000",
            ),
        )

    @property
    def _owner_edge(self):
        if self.owner and self.owner.node_id:
            yield Edge(
                kind=ek.HAS_PERSONAL_ACCESS_TOKEN,
                start=EdgePath(value=self.owner.node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self._org_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield from self._owner_edge
