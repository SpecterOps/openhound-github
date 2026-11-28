from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, ConfigDict

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.permissions import split_permission_groups
from openhound_github.models.pat_access import pat_access_edges
from openhound_github.models.branch_creation import branch_creation_edges
from openhound_github.pat_ids import collected_pat_node_id


class Permissions(BaseModel):
    model_config = ConfigDict(extra="allow")

    organization: dict | None = None
    repository: dict | None = None
    enterprise: dict | None = None
    account: dict | None = None


class Owner(BaseModel):
    login: str
    id: int
    type: str
    node_id: str


@dataclass
class GHPersonalAccessTokenProperties(GHNodeProperties):
    """PAT properties; entity-panel queries live in the extension schema.

    Attributes:
        environment_name: The name of the environment (GitHub organization) where the token has access.
        owner_id: The GitHub ID of the token owner.
        owner_node_id: The GraphQL node ID of the token owner.
        token_expires_at: The ISO 8601 timestamp of when the token expires.
        permissions_organization: Granted organization permissions as permission:access values.
        permissions_repository: Granted repository permissions as permission:access values.
        permissions_enterprise: Granted enterprise permissions as permission:access values.
        permissions_account: Granted account permissions as permission:access values.
        permissions_unclassified: Granted permissions absent from the shared catalog.
        token_last_used_at: The ISO 8601 timestamp of when the token was last used.
        access_granted_at: The ISO 8601 timestamp of when the token was granted to the organization.
        token_name: The user-assigned display name of the token.
        owner_login: The login handle of the user who owns the token.
        repository_selection: Whether the token has access to `all`, `subset`, or `none` of the organization's repositories.
        token_expired: Whether the token has expired.
    """

    environment_name: str
    owner_id: str | None = None
    # TODO: owner_node_id?
    owner_node_id: str | None = None
    token_expires_at: datetime | None = None
    token_last_used_at: datetime | None = None
    access_granted_at: datetime | None = None
    permissions_organization: list[str] | None = None
    permissions_repository: list[str] | None = None
    permissions_enterprise: list[str] | None = None
    permissions_account: list[str] | None = None
    permissions_unclassified: list[str] | None = None
    token_name: str | None = None
    owner_login: str | None = None
    repository_selection: str | None = None
    token_expired: bool | None = None


@app.asset(
    node=NodeDef(
        kind=nk.PERSONAL_ACCESS_TOKEN,
        description="GitHub Fine-Grained Personal Access Token",
        icon="key",
        properties=GHPersonalAccessTokenProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN,
            end=nk.ENTERPRISE,
            kind=ek.CAN_ACCESS,
            description="Credential targets declared enterprise permissions",
            traversable=False,
        ),
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
            end=nk.REPOSITORY,
            kind=ek.CAN_CREATE_BRANCH,
            description="PAT can create branches within its owner's effective authority",
            traversable=True,
        ),
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN,
            end=nk.SCOPE,
            kind=ek.CAN_CREATE_BRANCH,
            description="PAT can create branches throughout an authorized repository scope",
            traversable=True,
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

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

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

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str | None:
        """Identify the token's organization grant using its numeric API ID."""
        return collected_pat_node_id(
            self._lookup.org_database_id_for_login(self.org_login),
            self.id,
            org_login=self.org_login,
            resource="personal_access_tokens",
            request=False,
        )

    @property
    def as_node(self) -> GHNode | None:
        pid = self.node_id
        if pid is None:
            return None
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
                environmentid=self.org_node_id,
                environment_name=self.org_login,
                token_expires_at=self.token_expires_at,
                owner_id=self.owner.id if self.owner else None,
                owner_node_id=self.owner.node_id,
                **split_permission_groups(self.permissions.model_dump()),
                token_last_used_at=self.token_last_used_at,
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
    def _can_create_branch_edges(self):
        permissions = split_permission_groups(self.permissions.model_dump())
        if (
            self.token_expired
            or "contents:write" not in permissions["permissions_repository"]
            or self.repository_selection not in {"all", "subset", "selected"}
            or not self.owner.node_id
            or not self.org_node_id
        ):
            return
        now = datetime.now(timezone.utc)
        for expiration in (self.expires_at, self.token_expires_at):
            if expiration is not None:
                if expiration.tzinfo is None:
                    expiration = expiration.replace(tzinfo=timezone.utc)
                if expiration <= now:
                    return

        owner_id = self.owner.node_id.replace("\\", "\\\\").replace("'", "\\'")
        access_query = (
            f"MATCH p=(token:GH_PersonalAccessToken {{node_id:'{self.node_id}'}})"
            "-[:GH_CanAccess|GH_ScopedTo*1..2]->(repository:GH_Repository) "
            f"MATCH owner_access=(owner:GH_User {{node_id:'{owner_id}'}})"
            "-[:GH_HasRole|GH_HasBaseRole|GH_MemberOf*1..]->(:GH_RepoRole)"
            "-[:GH_CanCreateBranch]->(repository) "
            "WHERE 'contents:write' IN token.permissions_repository "
            "AND token.token_expired = false "
        )
        yield from branch_creation_edges(
            self._lookup,
            credential_node_id=self.node_id,
            org_login=self.org_login,
            org_node_id=self.org_node_id,
            allow_shared_scope=(
                self.repository_selection == "all"
                and self._lookup.pat_branch_creation_scope_authorized(
                    self.owner.node_id, self.org_login, self.id
                )
            ),
            resolve_repositories=lambda exclude_shared: (
                self._lookup.pat_branch_creation_repositories(
                    self.owner.node_id,
                    self.org_login,
                    self.id,
                    self.repository_selection,
                    exclude_shared=exclude_shared,
                )
            ),
            access_query=access_query,
            supporting_paths=("owner_access",),
            repository_evidence_queries={
                "owner_creation_capability": (
                    "MATCH protections=(repository)-[:GH_Contains]->(rule:GH_BranchProtectionRule) "
                    "RETURN p, owner_access, protections"
                ),
            },
        )

    @property
    def edges(self):
        if self.node_id is None:
            return
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
            permissions=split_permission_groups(self.permissions.model_dump()),
        )
        yield from self._owner_edge
        yield from self._can_create_branch_edges
