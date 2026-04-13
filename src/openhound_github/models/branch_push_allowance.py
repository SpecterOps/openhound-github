from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.BRANCH_PROTECTION_RULE,
            kind=ek.RESTRICTIONS_CAN_PUSH,
            description="Actor can push despite push restrictions",
            traversable=False,
        )
    ],
)
class BranchPushAllowance(BaseAsset):
    """One record from `branch_push_allowances` → GH_RestrictionsCanPush edge. No node."""

    rule_node_id: str
    actor_node_id: str
    actor_type: str
    actor_login: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.RESTRICTIONS_CAN_PUSH,
            start=EdgePath(value=self.actor_node_id, match_by="id"),
            end=EdgePath(value=self.rule_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
