from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

# from openhound_github.helpers import _b64


@app.asset(
    edges=[
        EdgeDef(
            start=nk.BRANCH,
            end=nk.ENVIRONMENT,
            kind=ek.HAS_ENVIRONMENT,
            description="Branch pattern can deploy to environment",
            traversable=False,
        )
    ],
)
class EnvironmentBranchPolicy(BaseAsset):
    """One record from `environment_branch_policies` → GH_HasEnvironment edge from synthetic policy ID. No node."""

    id: int
    node_id: str
    name: str

    environment_node_id: str
    environment_name: str
    repository_name: str
    repository_node_id: str

    @property
    def policy_id(self) -> str:
        # return _b64(f"{self.environment_node_id}_{self.name}")
        return f"{self.environment_node_id}_{self.name}"

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        # policy_id = _b64(f"{self.environment_node_id}_{self.pattern}")
        yield Edge(
            kind=ek.HAS_ENVIRONMENT,
            start=EdgePath(value=self.policy_id, match_by="id"),
            end=EdgePath(value=self.environment_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
