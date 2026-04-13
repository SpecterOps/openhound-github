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
            kind=ek.BYPASS_PULL_REQUEST_ALLOWANCES,
            description="Actor can bypass PR review requirements",
            traversable=False,
        )
    ],
)
class BranchPrBypassAllowance(BaseAsset):
    """One record from `branch_pr_bypass_allowances` → GH_BypassPullRequestAllowances edge. No node."""

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
            kind=ek.BYPASS_PULL_REQUEST_ALLOWANCES,
            start=EdgePath(value=self.actor_node_id, match_by="id"),
            end=EdgePath(value=self.rule_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
