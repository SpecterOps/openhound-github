from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class Owner(BaseModel):
    login: str
    node_id: str
    id: int
    type: str
    site_admin: bool


@dataclass
class GHPersonalAccessTokenRequestProperties(GHNodeProperties):
    """PAT request properties and accordion panel queries.
    
    Attributes:
        token_name: The user-assigned display name of the token.
        owner_login: The login handle of the user who submitted the request.
        repository_selection: Whether the request targets `all`, `subset`, or `none` of the organization's repositories.
        reason: The rationale provided by the requester for the access request.
        org_name: The org name property.
        query_organization_permissions: Query for organization permissions.
        query_user: Query for user.
        query_repositories: Query for repositories.
    """

    # TODO: Check for the following fields
    # owner_id, owner_node_id, toke_id, token_expires_at, token_last_used_at, permissions, and environment_name

    token_name: str | None = None
    owner_login: str | None = None
    repository_selection: str | None = None
    reason: str | None = None
    org_name: str | None = None
    query_organization_permissions: str | None = None
    query_user: str | None = None
    query_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
        description="GitHub Fine-Grained PAT Access Request",
        icon="key",
        properties=GHPersonalAccessTokenRequestProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            kind=ek.HAS_PERSONAL_ACCESS_TOKEN_REQUEST,
            description="User submitted PAT request",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            kind=ek.CONTAINS,
            description="Org contains PAT request",
            traversable=False,
        ),
    ],
)
class PersonalAccessTokenRequest(BaseAsset):
    """One record from `personal_access_token_requests` → one GH_PersonalAccessTokenRequest node + edges."""

    id: int
    reason: str | None = None
    owner: Owner
    created_at: datetime | None = None
    token_id: int | None = None
    token_name: str
    token_expired: bool
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    permissions: dict | None = None
    repositories_url: str | None = None
    repository_selection: str | None = None

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        """Construct a generated node id"""
        return f"GH_PATRequest_{self.org_node_id}_{self.id}"

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.PERSONAL_ACCESS_TOKEN_REQUEST],
            properties=GHPersonalAccessTokenRequestProperties(
                name=self.token_name,
                displayname=self.token_name,
                node_id=rid,
                environmentid=self.org_node_id,
                token_name=self.token_name,
                owner_login=self.owner.login,
                repository_selection=self.repository_selection,
                reason=self.reason,
                org_name=self.org_login,
                query_organization_permissions=f"MATCH p=(:GH_PersonalAccessTokenRequest {{node_id:'{rid}'}})-[:GH_CanAccess]->(:GH_Organization) RETURN p",
                query_user=f"MATCH p=(:GH_User)-[:GH_HasPersonalAccessTokenRequest]->(:GH_PersonalAccessTokenRequest {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_PersonalAccessTokenRequest {{node_id:'{rid}'}})-[:GH_CanAccess]->(:GH_Repository) RETURN p LIMIT 1000",
            ),
        )

    @property
    def _owner_edge(self):
        if self.owner and self.owner.node_id:
            yield Edge(
                kind=ek.HAS_PERSONAL_ACCESS_TOKEN_REQUEST,
                start=EdgePath(value=self.owner.node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
