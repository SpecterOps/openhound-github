from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHDeployKeyProperties(GHNodeProperties):
    """Repository deploy key properties and accordion panel queries.

    Attributes:
        github_id: The numeric GitHub deploy key ID.
        title: The user-assigned deploy key title.
        key: The public SSH key material.
        verified: Whether GitHub has verified the deploy key.
        enabled: Whether the deploy key is currently enabled.
        read_only: Whether the deploy key is restricted to read-only repository access.
        repository_permissions: Repository-scoped permissions in `scope:access` form.
        created_at: When the deploy key was created.
        last_used: When the deploy key was last used.
        added_by_login: The login of the user who added the deploy key.
        added_by_id: The node ID of the user who added the deploy key.
        repository_name: The full name of the containing repository.
        repository_id: The node_id of the containing repository.
        environment_name: The name of the environment (GitHub organization).
        query_repository: Query for the containing repository.
        query_added_by: Query for the user who added the deploy key.
    """

    github_id: int | None = None
    title: str | None = None
    key: str | None = None
    verified: bool | None = None
    enabled: bool | None = None
    read_only: bool | None = None
    repository_permissions: list[str] | None = None
    created_at: str | None = None
    last_used: str | None = None
    added_by_login: str | None = None
    added_by_id: str | None = None
    repository_name: str | None = None
    repository_id: str | None = None
    environment_name: str | None = None
    query_repository: str | None = None
    query_added_by: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.DEPLOY_KEY,
        description="GitHub Repository Deploy Key",
        icon="key",
        properties=GHDeployKeyProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.DEPLOY_KEY,
            kind=ek.CONTAINS,
            description="Repository contains deploy key",
            traversable=False,
        ),
        EdgeDef(
            start=nk.DEPLOY_KEY,
            end=nk.REPOSITORY,
            kind=ek.CAN_ACCESS,
            description="Deploy key can access repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.USER,
            end=nk.DEPLOY_KEY,
            kind=ek.ADDED_DEPLOY_KEY,
            description="User added deploy key",
            traversable=False,
        ),
    ],
)
class DeployKey(BaseAsset):
    """One record from `repository_deploy_keys` -> one GH_DeployKey node and access edges."""

    id: int
    key: str | None = None
    url: str | None = None
    title: str
    verified: bool | None = None
    enabled: bool | None = None
    created_at: datetime | None = None
    read_only: bool | None = None
    last_used: datetime | None = None
    added_by: str | dict | None = None

    # Additional
    org_login: str
    repository_name: str
    repository_node_id: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return f"GH_DeployKey_{self.repository_node_id}_{self.id}"

    @property
    def repository_permissions(self) -> list[str] | None:
        if self.read_only is None:
            return None
        return ["contents:read" if self.read_only else "contents:write"]

    @property
    def added_by_login(self) -> str | None:
        if isinstance(self.added_by, dict):
            return self.added_by.get("login")
        if isinstance(self.added_by, str):
            return self.added_by
        return None

    @property
    def added_by_node_id(self) -> str | None:
        if self.added_by_login:
            return self._lookup.user_node_id_for_login(
                self.org_login, self.added_by_login
            )
        return None

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.DEPLOY_KEY],
            properties=GHDeployKeyProperties(
                name=f"{self.repository_name}/{self.title}",
                displayname=self.title,
                node_id=self.node_id,
                github_id=self.id,
                title=self.title,
                key=self.key,
                verified=self.verified,
                enabled=self.enabled,
                read_only=self.read_only,
                repository_permissions=self.repository_permissions,
                created_at=str(self.created_at) if self.created_at else None,
                last_used=str(self.last_used) if self.last_used else None,
                added_by_login=self.added_by_login,
                added_by_id=self.added_by_node_id,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_repository=f"MATCH p=(:GH_DeployKey {{node_id:'{self.node_id}'}})-[:GH_CanAccess]->(:GH_Repository) RETURN p",
                query_added_by=f"MATCH p=(:GH_User)-[:GH_AddedDeployKey]->(:GH_DeployKey {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def _added_by_edge(self):
        if self.added_by_node_id:
            yield Edge(
                kind=ek.ADDED_DEPLOY_KEY,
                start=EdgePath(value=self.added_by_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.repository_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield from self._added_by_edge
