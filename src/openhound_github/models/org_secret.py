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
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    ORGANIZATION_SECRET_SCOPE_TYPE,
    PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    scope_node_id,
)


@dataclass
class GHOrgSecretProperties(GHNodeProperties):
    """Org secret properties and accordion panel queries.

    Attributes:
        visibility: The secret's visibility scope: `all` (all repos), `private` (private and internal repos), or `selected` (specific repos).
        environment_name: The name of the environment (GitHub organization).
        created_at: When the secret was created.
        updated_at: When the secret was last updated.
        query_visible_repositories: Query for visible repositories.
        selected_repositories_url: The selected repositories url property.
    """

    visibility: str | None = None
    environment_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    query_visible_repositories: str | None = None
    selected_repositories_url: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORG_SECRET,
        description="GitHub Organization Actions Secret",
        icon="lock",
        properties=GHOrgSecretProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.ORG_SECRET,
            kind=ek.CONTAINS,
            description="Org contains secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_SECRET,
            kind=ek.HAS_SECRET,
            description="Repository can access org secret",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCOPE,
            end=nk.ORG_SECRET,
            kind=ek.SCOPED_TO,
            description="Organization-secret scope applies to organization secret",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.SCOPE,
            kind=ek.HAS_SECRET,
            description="Repository can access organization-secret scope",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORG_SECRET,
            kind=ek.CAN_READ_SECRET,
            description="Org role can read org secret by creating a repository in scope",
            traversable=True,
        ),
    ],
)
class OrgSecret(BaseAsset):
    """One record from `organization_secrets` → one GH_OrgSecret node + GH_Contains from org."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    name: str
    created_at: datetime
    updated_at: datetime | None = None
    visibility: str

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return f"GH_OrgSecret_{self.org_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        sid = self.node_id
        return GHNode(
            kinds=[nk.ORG_SECRET, nk.SECRET],
            properties=GHOrgSecretProperties(
                name=self.name,
                displayname=self.name,
                node_id=sid,
                visibility=self.visibility,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
                query_visible_repositories=f"MATCH p=(:GH_Repository)-[:GH_HasSecret|GH_ScopedTo*1..2]->(:GH_OrgSecret {{node_id:'{sid}'}}) RETURN p",
            ),
        )

    @property
    def _all_repo_edges(self):
        if self.visibility == "all":
            yield Edge(
                kind=ek.SCOPED_TO,
                start=EdgePath(
                    value=scope_node_id(
                        self.org_node_id,
                        ORGANIZATION_SECRET_SCOPE_TYPE,
                        ALL_REPOSITORIES_SCOPE,
                    ),
                    match_by="id",
                ),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _private_repo_edges(self):
        if self.visibility == "private":
            yield Edge(
                kind=ek.SCOPED_TO,
                start=EdgePath(
                    value=scope_node_id(
                        self.org_node_id,
                        ORGANIZATION_SECRET_SCOPE_TYPE,
                        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
                    ),
                    match_by="id",
                ),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._contains_edge
        yield from self._all_repo_edges
        yield from self._private_repo_edges


@app.asset(
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_SECRET,
            kind=ek.HAS_SECRET,
            description="Repository can access org secret",
            traversable=True,
        ),
    ],
)
class SelectedOrgSecret(BaseAsset):
    """One record from `organization_secrets` → one GH_OrgSecret node + GH_Contains from org."""

    name: str
    repository_node_id: str
    repository_full_name: str
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return f"GH_OrgSecret_{self.org_node_id}_{self.name}"

    @property
    def as_node(self) -> None:
        return None

    @property
    def _has_secret_edge(self):
        yield Edge(
            kind=ek.HAS_SECRET,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )

    @property
    def edges(self):
        yield from self._has_secret_edge
