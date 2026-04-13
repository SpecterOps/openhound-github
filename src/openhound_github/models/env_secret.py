from dataclasses import dataclass, field
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnvironmentSecretProperties(GHNodeProperties):
    """Environment secret properties."""

    deployment_environment_name: str = field(
        default="",
        metadata={"description": "The name of the containing deployment environment."},
    )
    deployment_environmentid: str = field(
        default="",
        metadata={
            "description": "The node_id of the containing deployment environment."
        },
    )
    repository_name: str = ""
    repository_id: str = ""
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


@app.asset(
    node=NodeDef(
        kind=nk.ENVIRONMENT_SECRET,
        description="GitHub Environment Secret",
        icon="lock",
        properties=GHEnvironmentSecretProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENVIRONMENT,
            end=nk.ENVIRONMENT_SECRET,
            kind=ek.CONTAINS,
            description="Environment contains secret",
            traversable=False,
        )
    ],
)
class EnvironmentSecret(BaseAsset):
    """One record from `environment_secrets` → one GH_EnvironmentSecret node + GH_Contains edge from env."""

    name: str
    created_at: datetime
    updated_at: datetime | None = None
    visibility: str | None = None
    selected_repositories_url: str | None = None

    # Additional
    repository_name: str
    repository_node_id: str
    environment_name: str
    environment_node_id: str

    @property
    def node_id(self) -> str:
        return f"GH_EnvironmentSecret_{self.environment_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        sid = self.node_id
        return GHNode(
            kinds=[nk.ENVIRONMENT_SECRET, nk.SECRET],
            properties=GHEnvironmentSecretProperties(
                name=self.name,
                displayname=self.name,
                node_id=sid,
                deployment_environment_name=self.environment_name or "",
                deployment_environmentid=self.environment_node_id or "",
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self._lookup.org_login(),
                environmentid=self._lookup.org_id(),
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.environment_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
