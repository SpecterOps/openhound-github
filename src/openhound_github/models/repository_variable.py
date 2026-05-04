from dataclasses import dataclass, field
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHRepoVariableProperties(GHNodeProperties):
    """Repo variable properties and accordion panel queries."""

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
    value: str | None = field(
        default=None, metadata={"description": "The plaintext value of the variable."}
    )
    created_at: str | None = field(
        default=None, metadata={"description": "When the variable was created."}
    )
    updated_at: str | None = field(
        default=None, metadata={"description": "When the variable was last updated."}
    )
    query_visible_repositories: str = ""


@app.asset(
    node=NodeDef(
        kind=nk.REPO_VARIABLE,
        description="GitHub Repository Actions Variable",
        icon="lock-open",
        properties=GHRepoVariableProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_VARIABLE,
            kind=ek.CONTAINS,
            description="Repository contains variable",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_VARIABLE,
            kind=ek.HAS_VARIABLE,
            description="Repository has access to variable",
            traversable=False,
        ),
    ],
)
class RepoVariable(BaseAsset):
    """One record from `repository_variables` → one GH_RepoVariable node + GH_Contains and GH_HasVariable edges from repo."""

    name: str
    value: str
    created_at: datetime
    updated_at: datetime | None = None

    # Additional
    org_login: str
    repository_name: str = ""
    repository_node_id: str = ""

    @property
    def node_id(self) -> str:
        """Synthesize a unique node_id for the variable based on repo and variable name."""
        return f"GH_Variable_{self.repository_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        vid = self.node_id
        return GHNode(
            kinds=[nk.REPO_VARIABLE, nk.VARIABLE],
            properties=GHRepoVariableProperties(
                name=self.name,
                displayname=self.name,
                node_id=vid,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self._lookup.org_login(),
                environmentid=self._lookup.org_id(),
                value=self.value,
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
                query_visible_repositories=f"MATCH p=(:GH_RepoVariable {{node_id:'{vid}'}})<-[:GH_HasVariable]-(:GH_Repository) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_VARIABLE,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
