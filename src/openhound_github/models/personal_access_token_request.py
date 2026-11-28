from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.permissions import split_permission_groups
from openhound_github.models.pat_access import pat_access_edges
from openhound_github.pat_ids import pat_request_node_id


class Owner(BaseModel):
    login: str
    node_id: str
    id: int
    type: str
    site_admin: bool


@dataclass
class GHPersonalAccessTokenRequestProperties(GHNodeProperties):
    """PAT request properties; entity-panel queries live in the extension schema.

    Attributes:
        token_name: The user-assigned display name of the token.
        owner_login: The login handle of the user who submitted the request.
        repository_selection: Whether the request targets `all`, `subset`, or `none` of the organization's repositories.
        reason: The rationale provided by the requester for the access request.
        org_name: The org name property.
        permissions_organization: Requested organization permissions as permission:access values.
        permissions_repository: Requested repository permissions as permission:access values.
        permissions_enterprise: Requested enterprise permissions as permission:access values.
        permissions_account: Requested account permissions as permission:access values.
        permissions_unclassified: Requested permissions absent from the shared catalog.
    """

    # TODO: Check for the following fields
    # owner_id, owner_node_id, toke_id, token_expires_at, token_last_used_at, and environment_name

    token_name: str | None = None
    owner_login: str | None = None
    repository_selection: str | None = None
    reason: str | None = None
    org_name: str | None = None
    permissions_organization: list[str] | None = None
    permissions_repository: list[str] | None = None
    permissions_enterprise: list[str] | None = None
    permissions_account: list[str] | None = None
    permissions_unclassified: list[str] | None = None


@app.asset(
    node=NodeDef(
        kind=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
        description="GitHub Fine-Grained PAT Access Request",
        icon="key",
        properties=GHPersonalAccessTokenRequestProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            end=nk.ORGANIZATION,
            kind=ek.CAN_ACCESS,
            description="PAT request targets organization permissions",
            traversable=False,
        ),
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            end=nk.ENTERPRISE,
            kind=ek.CAN_ACCESS,
            description="PAT request targets declared enterprise permissions",
            traversable=False,
        ),
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
        """Identify this request independently of the underlying token."""
        return pat_request_node_id(
            self._lookup.org_database_id_for_login(self.org_login), self.id
        )

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
                **split_permission_groups(self.permissions),
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
        yield from self._owner_edge
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield from pat_access_edges(
            self._lookup,
            node_id=self.node_id,
            org_node_id=self.org_node_id,
            repository_selection=self.repository_selection,
            permissions=split_permission_groups(self.permissions),
        )
