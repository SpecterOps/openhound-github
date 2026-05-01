from dataclasses import dataclass, field
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef

from openhound_github.graph import (
    GHNode,
    GHNodeProperties,
)
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHEnvVariableProperties(GHNodeProperties):
    environment_name: str = field(
        metadata={"description": "The name of the environment (GitHub organization)."}
    )
    deployment_environment_name: str = field(
        metadata={
            "description": "The name of the deployment environment (GitHub organization)."
        }
    )
    value: str = field(metadata={"description": "The plaintext value of the variable."})
    created_at: datetime | None = field(
        metadata={"description": "When the variable was created."}
    )
    updated_at: datetime | None = field(
        metadata={"description": "When the variable was last updated."}
    )
    repository_name: str = field(
        metadata={"description": "The name of the containing repository."}
    )


@app.asset(
    node=NodeDef(
        kind=nk.ENVIRONMENT_VARIABLE,
        description="GitHub Environment Variable",
        icon="lock-open",
        properties=GHEnvVariableProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENVIRONMENT,
            end=nk.ENVIRONMENT_VARIABLE,
            kind=ek.CONTAINS,
            description="Environment contains variable",
            traversable=False,
        )
    ],
)
class EnvironmentVariable(BaseAsset):
    """One record from `environment_variables` → one GH_EnvironmentVariable node + GH_Contains edge from env."""

    name: str
    value: str
    created_at: datetime
    updated_at: datetime | None = None

    # Additional
    environment_node_id: str
    environment_name: str
    repository_name: str
    repository_node_id: str
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def node_id(self) -> str:
        return f"GH_EnvironmentVariable_{self.environment_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        vid = self.node_id
        return GHNode(
            kinds=[nk.ENVIRONMENT_VARIABLE, nk.VARIABLE],
            properties=GHEnvVariableProperties(
                name=self.name,
                displayname=self.name,
                node_id=vid,
                deployment_environment_name=self.environment_name,
                environment_name=self.org_login or self._lookup.org_login(),
                repository_name=self.repository_name,
                environmentid=self.org_node_id or self._lookup.org_id(),
                updated_at=self.updated_at,
                created_at=self.created_at,
                value=self.value,
            ),
        )

    @property
    def edges(self):
        # TODO: Check if this should indeed not return CONTAINS edge
        return []
        # yield Edge(
        #     kind=ek.CONTAINS,
        #     start=EdgePath(value=self.environment_node_id, match_by="id"),
        #     end=EdgePath(value=self.node_id, match_by="id"),
        #     properties=EdgeProperties(traversable=False),
        # )
