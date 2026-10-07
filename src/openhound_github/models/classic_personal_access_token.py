from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHClassicPersonalAccessTokenProperties(GHNodeProperties):
    """Metadata from the enterprise credential inventory export.

    Attributes:
        credential_id: GitHub's ID for this classic personal access token.
        owner_id: GitHub's numeric ID for the token owner.
        owner_login: Login of the token owner.
        scopes: OAuth scopes granted to the token.
        credential_state: Whether GitHub reports the credential as active, expired, revoked, or deleted.
        expiry_status: Whether expiration is scheduled, never, or unknown.
        enterprise_authorized: Whether the credential is authorized directly for the enterprise.
        authorization_count: Total organization authorizations plus enterprise authorization.
        inventory_as_of: Timestamp of the export snapshot used to observe the token.
        created_at: Token creation time reported by GitHub.
        last_used_at: Last use time reported by GitHub.
        expires_at: Token expiration time reported by GitHub.
        authorized_organizations: Organizations with a reported credential authorization.
        environment_name: Enterprise environment name.
        enterprise_name: Enterprise from which the inventory was exported.
    """

    credential_id: int | None = None
    owner_id: int | None = None
    owner_login: str | None = None
    scopes: list[str] | None = None
    credential_state: str | None = None
    expiry_status: str | None = None
    enterprise_authorized: bool | None = None
    authorization_count: int | None = None
    inventory_as_of: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    authorized_organizations: list[str] | None = None
    environment_name: str | None = None
    enterprise_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.CLASSIC_PERSONAL_ACCESS_TOKEN,
        description="GitHub classic personal access token in an enterprise credential inventory",
        icon="key",
        properties=GHClassicPersonalAccessTokenProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.CLASSIC_PERSONAL_ACCESS_TOKEN,
            kind=ek.CONTAINS,
            description="Enterprise inventory contains classic PAT",
            traversable=False,
        ),
        EdgeDef(
            start=nk.USER,
            end=nk.CLASSIC_PERSONAL_ACCESS_TOKEN,
            kind=ek.HAS_PERSONAL_ACCESS_TOKEN,
            description="User owns classic PAT",
            traversable=False,
        ),
        EdgeDef(
            start=nk.CLASSIC_PERSONAL_ACCESS_TOKEN,
            end=nk.ORGANIZATION,
            kind=ek.AUTHORIZED_FOR_ORGANIZATION,
            description="Classic PAT has a recorded organization authorization",
            traversable=False,
        ),
    ],
)
class ClassicPersonalAccessToken(BaseAsset):
    """One deduplicated classic PAT from an enterprise credential inventory export."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    credential_id: int
    display_name: str | None = None
    owner_id: int | None = None
    owner_login: str | None = None
    scopes: list[str] | None = None
    credential_state: str | None = None
    expiry_status: str | None = None
    enterprise_authorized: bool | None = None
    authorization_count: int | None = None
    inventory_as_of: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    authorized_organizations: list[str]
    enterprise_node_id: str
    enterprise_name: str

    @property
    def node_id(self) -> str:
        return f"GH_CLASSIC_PAT_{self.enterprise_node_id}_{self.credential_id}"

    @property
    def as_node(self) -> GHNode:
        name = self.display_name or f"Classic PAT {self.credential_id}"
        return GHNode(
            kinds=[nk.CLASSIC_PERSONAL_ACCESS_TOKEN],
            properties=GHClassicPersonalAccessTokenProperties(
                name=name,
                displayname=name,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_name,
                credential_id=self.credential_id,
                owner_id=self.owner_id,
                owner_login=self.owner_login,
                scopes=self.scopes,
                credential_state=self.credential_state,
                expiry_status=self.expiry_status,
                enterprise_authorized=self.enterprise_authorized,
                authorization_count=self.authorization_count,
                inventory_as_of=self.inventory_as_of,
                created_at=self.created_at,
                last_used_at=self.last_used_at,
                expires_at=self.expires_at,
                authorized_organizations=self.authorized_organizations,
                enterprise_name=self.enterprise_name,
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        if self.owner_id is not None:
            owner_node_id = self._lookup.enterprise_user_id_for_database_id(
                self.owner_id
            )
            if owner_node_id:
                yield Edge(
                    kind=ek.HAS_PERSONAL_ACCESS_TOKEN,
                    start=EdgePath(value=owner_node_id, match_by="id"),
                    end=EdgePath(value=self.node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )
        for login in self.authorized_organizations:
            org_node_id = self._lookup.enterprise_organization_id_for_login(login)
            if org_node_id:
                yield Edge(
                    kind=ek.AUTHORIZED_FOR_ORGANIZATION,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=org_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )
