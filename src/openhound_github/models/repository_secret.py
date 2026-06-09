from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHRepoSecretProperties(GHNodeProperties):
    """Repo secret properties and accordion panel queries.
    
    Attributes:
        repository_name: The name of the containing repository.
        repository_id: The node_id of the containing repository.
        environment_name: The name of the environment (GitHub organization).
        created_at: When the secret was created.
        updated_at: When the secret was last updated.
        visibility: The secret's visibility scope.
        query_visible_repositories: Query for visible repositories.
    """

    repository_name: str | None = None
    repository_id: str | None = None
    environment_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    visibility: str | None = None
    query_visible_repositories: str | None = None


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
    repository_name: str | None = None
    repository_node_id: str | None = None

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

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
                environment_name=self.org_login,
                environmentid=self.org_node_id,
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
