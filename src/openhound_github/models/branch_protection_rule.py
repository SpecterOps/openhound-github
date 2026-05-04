from dataclasses import dataclass, field
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class BranchProtectionRuleActor(BaseModel):
    """Actor involved in branch protection rule bypass/push allowances."""

    rule_node_id: str
    actor_node_id: str
    actor_type: str  # "user" or "team"
    actor_login: str  # login for users, slug for teams


@dataclass
class GHBranchProtectionRuleProperties(GHNodeProperties):
    """Branch protection rule properties and accordion panel queries."""

    pattern: str = field(
        default="",
        metadata={
            "description": "The branch name pattern this rule applies to (e.g., `main`, `release/*`)."
        },
    )
    repository_name: str = ""
    repository_id: str = ""
    environment_name: str = field(
        default="", metadata={"description": "The GitHub organization login name."}
    )
    enforce_admins: bool | None = field(
        default=None,
        metadata={
            "description": "Whether branch protection rules are enforced for administrators."
        },
    )
    lock_branch: bool | None = field(
        default=None,
        metadata={"description": "Whether the branch is locked (read-only)."},
    )
    blocks_creations: bool | None = field(
        default=None,
        metadata={
            "description": "Whether creating branches matching this pattern is restricted. Only effective when `push_restrictions` is also `true`; silently reverts to `false` otherwise."
        },
    )
    required_pull_request_reviews: bool | None = field(
        default=None,
        metadata={
            "description": "Whether pull request reviews are required before merging."
        },
    )
    required_approving_review_count: int | None = field(
        default=None,
        metadata={"description": "The number of approving reviews required."},
    )
    require_code_owner_reviews: bool | None = field(
        default=None,
        metadata={"description": "Whether reviews from code owners are required."},
    )
    require_last_push_approval: bool | None = field(
        default=None,
        metadata={
            "description": "Whether the last push must be approved by someone other than the pusher."
        },
    )
    push_restrictions: bool | None = field(
        default=None,
        metadata={
            "description": "Whether push access is restricted to specific users/teams."
        },
    )
    requires_status_checks: bool | None = field(
        default=None,
        metadata={"description": "Whether status checks must pass before merging."},
    )
    requires_strict_status_checks: bool | None = field(
        default=None,
        metadata={
            "description": "Whether branches must be up to date with the base branch before merging."
        },
    )
    dismisses_stale_reviews: bool | None = field(
        default=None,
        metadata={
            "description": "Whether new commits dismiss previously approved reviews."
        },
    )
    allows_force_pushes: bool | None = field(
        default=None,
        metadata={
            "description": "Whether force pushes are allowed to matching branches."
        },
    )
    allows_deletions: bool | None = field(
        default=None,
        metadata={"description": "Whether matching branches can be deleted."},
    )
    query_user_exceptions: str = ""
    query_branches: str = ""


class Actor(BaseModel):
    id: str | None = None
    slug: str | None = None
    login: str | None = None


class NodeActor(BaseModel):
    actor: Actor


class BypassAllowances(BaseModel):
    nodes: list[NodeActor]


class PushAllowances(BaseModel):
    nodes: list[NodeActor]


@app.asset(
    node=NodeDef(
        kind=nk.BRANCH_PROTECTION_RULE,
        description="GitHub Branch Protection Rule",
        icon="shield",
        properties=GHBranchProtectionRuleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.BRANCH_PROTECTION_RULE,
            kind=ek.CONTAINS,
            description="Repository contains branch protection rule",
            traversable=False,
        ),
    ],
)
class BranchProtectionRule(BaseAsset):
    """One record from `branch_protection_rules` → one GH_BranchProtectionRule node + GH_Contains edge from repo."""

    model_config = ConfigDict(populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: str
    pattern: str
    is_admin_enforced: bool = Field(alias="isAdminEnforced")
    lock_branch: bool = Field(alias="lockBranch")
    blocks_creations: bool = Field(alias="blocksCreations")
    requires_approving_reviews: bool = Field(alias="requiresApprovingReviews")
    required_approving_review_count: int | None = Field(
        alias="requiredApprovingReviewCount", default=None
    )
    requires_code_owner_reviews: bool = Field(alias="requiresCodeOwnerReviews")
    require_last_push_approval: bool = Field(alias="requireLastPushApproval")
    restricts_pushes: bool = Field(alias="restrictsPushes")
    requires_status_checks: bool = Field(alias="requiresStatusChecks")
    requires_strict_status_checks: bool = Field(alias="requiresStrictStatusChecks")
    dismisses_stale_reviews: bool = Field(alias="dismissesStaleReviews")
    allows_force_pushes: bool = Field(alias="allowsForcePushes")
    allows_deletions: bool = Field(alias="allowsDeletions")

    bypass_pull_request_allowances: BypassAllowances | None = Field(
        alias="bypassPullRequestAllowances", default=None
    )
    push_allowances: PushAllowances | None = Field(alias="pushAllowances", default=None)

    # Additional
    org_login: str
    repository_node_id: str
    repository_name: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.BRANCH_PROTECTION_RULE],
            properties=GHBranchProtectionRuleProperties(
                name=self.pattern,
                displayname=self.pattern,
                node_id=self.node_id,
                pattern=self.pattern,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                enforce_admins=self.is_admin_enforced,
                lock_branch=self.lock_branch,
                blocks_creations=self.blocks_creations,
                required_pull_request_reviews=self.requires_approving_reviews,
                required_approving_review_count=self.required_approving_review_count,
                require_code_owner_reviews=self.requires_code_owner_reviews,
                require_last_push_approval=self.require_last_push_approval,
                push_restrictions=self.restricts_pushes,
                requires_status_checks=self.requires_status_checks,
                requires_strict_status_checks=self.requires_strict_status_checks,
                dismisses_stale_reviews=self.dismisses_stale_reviews,
                allows_force_pushes=self.allows_force_pushes,
                allows_deletions=self.allows_deletions,
                query_user_exceptions=(
                    f"MATCH p=(:GH_User)-[]->(:GH_BranchProtectionRule {{node_id:'{self.node_id}'}}) RETURN p"
                ),
                query_branches=(
                    f"MATCH p=(:GH_BranchProtectionRule {{node_id:'{self.node_id}'}})-[:GH_ProtectedBy]->(:GH_Branch) RETURN p"
                ),
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
