from dataclasses import dataclass, field
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
class GHOrgSecretProperties(GHNodeProperties):
    """Org secret properties and accordion panel queries."""

    visibility: str = field(
        default="",
        metadata={
            "description": "The secret's visibility scope: `all` (all repos), `private` (private and internal repos), or `selected` (specific repos)."
        },
    )
    environment_name: str = field(
        default="",
        metadata={"description": "The name of the environment (GitHub organization)."},
    )
    created_at: str | None = field(
        default=None, metadata={"description": "When the secret was created."}
    )
    updated_at: str | None = field(
        default=None, metadata={"description": "When the secret was last updated."}
    )
    query_visible_repositories: str = ""
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
                query_visible_repositories=f"MATCH p=(:GH_OrgSecret {{node_id:'{sid}'}})<-[:GH_HasSecret]-(:GH_Repository) RETURN p",
            ),
        )

    @property
    def _all_repo_edges(self):
        if self.visibility == "all":
            for repo in self._lookup.repository_node_ids_for_org(self.org_login):
                for repo_node_id in repo:
                    yield Edge(
                        kind=ek.HAS_SECRET,
                        start=EdgePath(value=repo_node_id, match_by="id"),
                        end=EdgePath(value=self.node_id, match_by="id"),
                        properties=EdgeProperties(traversable=True),
                    )

    @property
    def _private_repo_edges(self):
        if self.visibility == "private":
            for repo in self._lookup.private_repository_node_ids_for_org(self.org_login):
                for repo_node_id in repo:
                    yield Edge(
                        kind=ek.HAS_SECRET,
                        start=EdgePath(value=repo_node_id, match_by="id"),
                        end=EdgePath(value=self.node_id, match_by="id"),
                        properties=EdgeProperties(traversable=True),
                    )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
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
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

        yield Edge(
            kind=ek.HAS_SECRET,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
