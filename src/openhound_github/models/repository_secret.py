from dataclasses import dataclass, field
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHRepoSecretProperties(GHNodeProperties):
    """Repo secret properties and accordion panel queries."""

    repository_name: str = field(
        default="", metadata={"description": "The name of the containing repository."}
    )
    repository_id: str = field(
        default="",
        metadata={"description": "The node_id of the containing repository."},
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
    visibility: str | None = field(
        default=None, metadata={"description": "The secret's visibility scope."}
    )
    query_visible_repositories: str = ""


@app.asset(
    node=NodeDef(
        kind=nk.REPO_SECRET,
        description="GitHub Repository Actions Secret",
        icon="lock",
        properties=GHRepoSecretProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_SECRET,
            kind=ek.CONTAINS,
            description="Repository contains secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_SECRET,
            kind=ek.HAS_SECRET,
            description="Repository has access to secret",
            traversable=True,
        ),
    ],
)
class RepoSecret(BaseAsset):
    """One record from `repository_secrets` → one GH_RepoSecret node + GH_Contains and GH_HasSecret edges from repo."""

    name: str
    created_at: datetime
    updated_at: datetime | None = None
    visibility: str | None = None
    selected_repositories_url: str | None = None

    # Additional
    org_login: str
    repository_name: str = ""
    repository_node_id: str = ""

    @property
    def node_id(self) -> str:
        return f"GH_Secret_{self.repository_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        sid = self.node_id
        return GHNode(
            kinds=[nk.REPO_SECRET, nk.SECRET],
            properties=GHRepoSecretProperties(
                name=self.name,
                displayname=self.name,
                node_id=sid,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self._lookup.org_login(),
                environmentid=self._lookup.org_id(),
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
                visibility=self.visibility,
                query_visible_repositories=f"MATCH p=(:GH_RepoSecret {{node_id:'{sid}'}})<-[:GH_HasSecret]-(:GH_Repository) RETURN p",
            ),
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
            kind=ek.HAS_SECRET,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
