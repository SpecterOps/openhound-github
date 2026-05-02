from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

DEFAULT_REPO_ROLES: list[dict[str, str | None]] = [
    {
        "name": "read",
        "base_role": None,
    },
    {
        "name": "triage",
        "base_role": "read",
    },
    {
        "name": "write",
        "base_role": None,
    },
    {
        "name": "maintain",
        "base_role": "write",
    },
    {
        "name": "admin",
        "base_role": None,
    },
]


# Direct permission edges emitted by each default repo role → repository
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "read": [ek.READ_REPO_CONTENTS],
    "triage": [
        ek.ADD_LABEL,
        ek.REMOVE_LABEL,
        ek.CLOSE_ISSUE,
        ek.REOPEN_ISSUE,
        ek.CLOSE_PR,
        ek.REOPEN_PR,
        ek.ADD_ASSIGNEE,
        ek.REMOVE_ASSIGNEE,
        ek.REQUEST_PR_REVIEW,
        ek.MARK_AS_DUPLICATE,
        ek.SET_MILESTONE,
        ek.SET_ISSUE_TYPE,
        ek.DELETE_DISCUSSION,
        ek.TOGGLE_DISCUSSION_ANSWER,
        ek.TOGGLE_DISCUSSION_COMMENT_MINIMIZE,
        ek.CREATE_DISCUSSION_CATEGORY,
        ek.EDIT_DISCUSSION_CATEGORY,
        ek.CONVERT_ISSUES_TO_DISCUSSIONS,
        ek.CLOSE_DISCUSSION,
        ek.REOPEN_DISCUSSION,
        ek.EDIT_CATEGORY_ON_DISCUSSION,
        ek.EDIT_DISCUSSION_COMMENT,
        ek.DELETE_DISCUSSION_COMMENT,
    ],
    "write": [
        ek.READ_REPO_CONTENTS,
        ek.WRITE_REPO_CONTENTS,
        ek.ADD_LABEL,
        ek.REMOVE_LABEL,
        ek.CLOSE_ISSUE,
        ek.REOPEN_ISSUE,
        # ek.READ_REPO_PULL_REQUEST,
        ek.WRITE_REPO_PULL_REQUESTS,
        ek.CLOSE_PR,
        ek.REOPEN_PR,
        ek.SET_ISSUE_TYPE,
        ek.ADD_ASSIGNEE,
        ek.REMOVE_ASSIGNEE,
        ek.REQUEST_PR_REVIEW,
        ek.MARK_AS_DUPLICATE,
        ek.SET_MILESTONE,
        ek.READ_CODE_SCANNING,
        ek.WRITE_CODE_SCANNING,
        ek.DELETE_DISCUSSION,
        ek.TOGGLE_DISCUSSION_ANSWER,
        ek.TOGGLE_DISCUSSION_COMMENT_MINIMIZE,
        ek.MANAGE_DISCUSSION_BADGES,
        # ek.MANAGE_DISCUSSION_SPOTLIGHTS,
        ek.CREATE_DISCUSSION_CATEGORY,
        ek.EDIT_DISCUSSION_CATEGORY,
        ek.CONVERT_ISSUES_TO_DISCUSSIONS,
        ek.CLOSE_DISCUSSION,
        ek.REOPEN_DISCUSSION,
        ek.EDIT_CATEGORY_ON_DISCUSSION,
        ek.EDIT_DISCUSSION_COMMENT,
        ek.DELETE_DISCUSSION_COMMENT,
        ek.VIEW_DEPENDABOT_ALERTS,
        ek.RESOLVE_DEPENDABOT_ALERTS,
    ],
    "maintain": [
        ek.PUSH_PROTECTED_BRANCH,
        ek.MANAGE_TOPICS,
        ek.MANAGE_WIKI_SETTINGS,
        ek.MANAGE_PROJECTS_SETTINGS,
        ek.MANAGE_MERGE_TYPES_SETTINGS,
        ek.MANAGE_PAGES_SETTINGS,
        ek.EDIT_REPO_METADATA,
        ek.SET_INTERACTION_LIMITS,
        ek.SET_SOCIAL_PREVIEW,
        ek.CREATE_TAG,
        ek.EDIT_REPO_ANNOUNCEMENT_BANNERS,
    ],
    "admin": [
        ek.ADMIN_TO,
        ek.READ_REPO_CONTENTS,
        ek.WRITE_REPO_CONTENTS,
        ek.ADD_LABEL,
        ek.REMOVE_LABEL,
        ek.CLOSE_ISSUE,
        ek.REOPEN_ISSUE,
        # ek.READ_REPO_PULL_REQUEST,   # commented out in PS (githound.ps1)
        ek.WRITE_REPO_PULL_REQUESTS,
        ek.CLOSE_PR,
        ek.REOPEN_PR,
        ek.ADD_ASSIGNEE,
        ek.DELETE_ISSUE,
        ek.REMOVE_ASSIGNEE,
        ek.REQUEST_PR_REVIEW,
        ek.MARK_AS_DUPLICATE,
        ek.SET_MILESTONE,
        ek.SET_ISSUE_TYPE,
        ek.MANAGE_TOPICS,
        ek.MANAGE_WIKI_SETTINGS,
        ek.MANAGE_PROJECTS_SETTINGS,
        ek.MANAGE_MERGE_TYPES_SETTINGS,
        ek.MANAGE_PAGES_SETTINGS,
        ek.MANAGE_WEBHOOKS,
        ek.MANAGE_DEPLOY_KEYS,
        ek.EDIT_REPO_METADATA,
        ek.SET_INTERACTION_LIMITS,
        ek.SET_SOCIAL_PREVIEW,
        ek.PUSH_PROTECTED_BRANCH,
        ek.READ_CODE_SCANNING,
        ek.WRITE_CODE_SCANNING,
        ek.DELETE_ALERTS_CODE_SCANNING,
        ek.VIEW_SECRET_SCANNING_ALERTS,
        ek.RESOLVE_SECRET_SCANNING_ALERTS,
        ek.RUN_ORG_MIGRATION,
        ek.CREATE_DISCUSSION_CATEGORY,
        ek.EDIT_DISCUSSION_CATEGORY,
        ek.DELETE_DISCUSSION,
        # ek.MANAGE_DISCUSSION_SPOTLIGHTS,   # commented out in PS (githound.ps1)
        ek.TOGGLE_DISCUSSION_ANSWER,
        ek.TOGGLE_DISCUSSION_COMMENT_MINIMIZE,
        ek.CONVERT_ISSUES_TO_DISCUSSIONS,
        ek.CREATE_TAG,
        ek.DELETE_TAG,
        ek.VIEW_DEPENDABOT_ALERTS,
        ek.RESOLVE_DEPENDABOT_ALERTS,
        ek.BYPASS_BRANCH_PROTECTION,
        ek.MANAGE_SECURITY_PRODUCTS,
        ek.MANAGE_REPO_SECURITY_PRODUCTS,
        ek.EDIT_REPO_PROTECTIONS,
        ek.EDIT_REPO_ANNOUNCEMENT_BANNERS,
        ek.CLOSE_DISCUSSION,
        ek.REOPEN_DISCUSSION,
        ek.EDIT_CATEGORY_ON_DISCUSSION,
        ek.MANAGE_DISCUSSION_BADGES,
        ek.EDIT_DISCUSSION_COMMENT,
        ek.DELETE_DISCUSSION_COMMENT,
        ek.JUMP_MERGE_QUEUE,
        ek.CREATE_SOLO_MERGE_QUEUE_ENTRY,
        ek.EDIT_REPO_CUSTOM_PROPERTIES_VALUES,
    ],
}


class Organization(BaseModel):
    login: str
    url: str
    id: int
    description: str | None = None
    type: str
    node_id: str


class BaseRepoRole(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    organization: Organization | None = None
    base_role: str
    org_node_id: str | None = None
    org_login: str | None = None


@dataclass
class GHRepoRoleProperties(GHNodeProperties):
    """Repository role-specific properties and accordion panel queries.

    Attributes:
        short_name: The short role name (e.g., `read`, `write`, `admin`, `triage`, `maintain`, or custom role name).
        repository_name: The name of the repository this role belongs to.
        repository_id: The node_id of the repository this role belongs to.
        environment_name: The name of the environment (GitHub organization).
        type: `default` for built-in roles or `custom` for custom repository roles.
        query_explicit_users: OpenGraph query for related explicit users.
        query_explicit_teams: OpenGraph query for related explicit teams.
        query_unrolled_members: OpenGraph query for related unrolled members.
        query_repository_permissions: OpenGraph query for related repository permissions.
    """

    short_name: str
    repository_name: str
    repository_id: str
    environment_name: str
    type: str
    query_explicit_users: str | None = None
    query_explicit_teams: str | None = None
    query_unrolled_members: str | None = None
    query_repository_permissions: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.REPO_ROLE,
        description="GitHub Repository Role",
        icon="user-tie",
        properties=GHRepoRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.READ_REPO_CONTENTS,
            description="Role can read repo contents",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.WRITE_REPO_CONTENTS,
            description="Role can write repo contents",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.WRITE_REPO_PULL_REQUESTS,
            description="Role can write pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.ADMIN_TO,
            description="Role has admin access to repo",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPO_ROLE,
            kind=ek.HAS_BASE_ROLE,
            description="Role inherits from base role",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.BYPASS_BRANCH_PROTECTION,
            description="Role can bypass branch protection rules",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.PUSH_PROTECTED_BRANCH,
            description="Role can push to protected branches",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_REPO_PROTECTIONS,
            description="Role can edit repository branch protection settings",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.VIEW_SECRET_SCANNING_ALERTS,
            description="Role can view secret scanning alerts",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.RESOLVE_SECRET_SCANNING_ALERTS,
            description="Role can resolve secret scanning alerts",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.DELETE_ALERTS_CODE_SCANNING,
            description="Role can delete code scanning alerts",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.RUN_ORG_MIGRATION,
            description="Role can run organization migrations on the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_SECURITY_PRODUCTS,
            description="Role can manage security products for the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_REPO_SECURITY_PRODUCTS,
            description="Role can manage repository-level security products",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_WEBHOOKS,
            description="Role can manage repository webhooks",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_DEPLOY_KEYS,
            description="Role can manage repository deploy keys",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CAN_CREATE_BRANCH,
            description="Role can create new branches in the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.BRANCH,
            kind=ek.CAN_WRITE_BRANCH,
            description="Role can push commits to this branch",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.BRANCH,
            kind=ek.CAN_EDIT_PROTECTION,
            description="Role can modify or remove the branch protection rule governing this branch",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.READ_CODE_SCANNING,
            description="Role can read code scanning results",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.WRITE_CODE_SCANNING,
            description="Role can write code scanning results",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.VIEW_DEPENDABOT_ALERTS,
            description="Role can view Dependabot alerts",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.RESOLVE_DEPENDABOT_ALERTS,
            description="Role can resolve Dependabot alerts",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_TOPICS,
            description="Role can manage repository topics",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_WIKI_SETTINGS,
            description="Role can manage wiki settings",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_PROJECTS_SETTINGS,
            description="Role can manage projects settings",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_MERGE_TYPES_SETTINGS,
            description="Role can manage merge type settings",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_PAGES_SETTINGS,
            description="Role can manage GitHub Pages settings",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_REPO_METADATA,
            description="Role can edit repository metadata (name, description, etc.)",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.SET_INTERACTION_LIMITS,
            description="Role can set interaction limits on the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.SET_SOCIAL_PREVIEW,
            description="Role can set the repository social preview image",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_REPO_ANNOUNCEMENT_BANNERS,
            description="Role can edit repository announcement banners",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_REPO_CUSTOM_PROPERTIES_VALUES,
            description="Role can edit custom property values on the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CREATE_TAG,
            description="Role can create tags in the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.DELETE_TAG,
            description="Role can delete tags in the repository",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.JUMP_MERGE_QUEUE,
            description="Role can jump the merge queue",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CREATE_SOLO_MERGE_QUEUE_ENTRY,
            description="Role can create a solo merge queue entry",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.ADD_LABEL,
            description="Role can add labels to issues and pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REMOVE_LABEL,
            description="Role can remove labels from issues and pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CLOSE_ISSUE,
            description="Role can close issues",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REOPEN_ISSUE,
            description="Role can reopen issues",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.DELETE_ISSUE,
            description="Role can delete issues",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CLOSE_PR,
            description="Role can close pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REOPEN_PR,
            description="Role can reopen pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.ADD_ASSIGNEE,
            description="Role can add assignees to issues and pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REMOVE_ASSIGNEE,
            description="Role can remove assignees from issues and pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REQUEST_PR_REVIEW,
            description="Role can request pull request reviews",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MARK_AS_DUPLICATE,
            description="Role can mark issues or pull requests as duplicates",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.SET_MILESTONE,
            description="Role can set milestones on issues and pull requests",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.SET_ISSUE_TYPE,
            description="Role can set issue types",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.DELETE_DISCUSSION,
            description="Role can delete discussions",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.TOGGLE_DISCUSSION_ANSWER,
            description="Role can toggle the accepted answer on a discussion",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.TOGGLE_DISCUSSION_COMMENT_MINIMIZE,
            description="Role can minimize or un-minimize discussion comments",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CREATE_DISCUSSION_CATEGORY,
            description="Role can create discussion categories",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_DISCUSSION_CATEGORY,
            description="Role can edit discussion categories",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CONVERT_ISSUES_TO_DISCUSSIONS,
            description="Role can convert issues to discussions",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.CLOSE_DISCUSSION,
            description="Role can close discussions",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.REOPEN_DISCUSSION,
            description="Role can reopen discussions",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_CATEGORY_ON_DISCUSSION,
            description="Role can edit the category on a discussion",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.MANAGE_DISCUSSION_BADGES,
            description="Role can manage discussion badges",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.EDIT_DISCUSSION_COMMENT,
            description="Role can edit discussion comments",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.REPOSITORY,
            kind=ek.DELETE_DISCUSSION_COMMENT,
            description="Role can delete discussion comments",
            traversable=False,
        ),
    ],
)
class RepoRole(BaseAsset):
    """One record from the `repo_roles` DLT table → one GH_RepoRole node + permission/hierarchy edges."""

    id: int
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    organization: Organization | None = None
    base_role: str | None = None

    # Additional
    type: str
    repository_node_id: str
    repository_name: str
    repository_full_name: str
    repository_visibility: str | None = None
    org_node_id_value: str | None = Field(alias="org_node_id", default=None)
    org_login: str | None = None

    @property
    def node_id(self) -> str:
        """Construct a synthetic node_id for this repo role based on org/repo/role name. This is needed to link users/teams to their roles via edges, since GH doesn't return unique IDs for custom roles."""
        return f"{self.repository_node_id}_{self.name}"

    @property
    def org_node_id(self) -> str:
        return self.org_node_id_value or self._lookup.org_id()

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=["GH_RepoRole", "GH_Role"],
            properties=GHRepoRoleProperties(
                name=f"{self.repository_full_name}/{self.name}",
                displayname=self.name,
                node_id=rid,
                short_name=self.name,
                type=self.type,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self.org_login or self._lookup.org_login(),
                environmentid=self.org_node_id,
                query_explicit_users=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_RepoRole {{node_id:'{rid}'}}) RETURN p",
                query_explicit_teams=f"MATCH p=(:GH_Team)-[:GH_HasRole]->(:GH_RepoRole {{node_id:'{rid}'}}) RETURN p",
                query_unrolled_members=(
                    f"MATCH p=(role:GH_Role)-[:GH_HasRole|GH_HasBaseRole|GH_MemberOf|GH_ReadRepoContents*1..]->(reporole:GH_RepoRole {{node_id:'{rid}'}}) "
                    f"MATCH p1=(role)<-[:GH_HasRole]-(:GH_User) "
                    f"OPTIONAL MATCH p2=(reporole)<-[:GH_HasRole]-(:GH_User) RETURN p,p1,p2"
                ),
                query_repository_permissions=f"MATCH p=(:GH_RepoRole {{node_id:'{rid}'}})-[*1..]->(:GH_Repository) RETURN p",
            ),
        )

    @property
    def _default_edges(self):
        if self.type == "default":
            # Org-level all_repo_* → this role (traversable)
            yield Edge(
                kind=ek.HAS_BASE_ROLE,
                start=EdgePath(
                    value=f"{self.org_node_id}_all_repo_{self.name}",
                    match_by="id",
                ),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

            # Direct permission edges → repo
            for kind in DEFAULT_ROLE_PERMISSIONS.get(self.name, []):
                yield Edge(
                    kind=kind,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.repository_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=(kind == "GH_AdminTo")),
                )

            # Internal repos: org members get read access by default
            if self.name == "read" and self.repository_visibility == "internal":
                yield Edge(
                    kind=ek.HAS_ROLE,
                    start=EdgePath(value=f"{self.org_node_id}_members", match_by="id"),
                    end=EdgePath(value=self.node_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    # @property
    # def _custom_edges(self):
    #     if self.type == "custom":
    #         for perm in self.permissions:
    #             yield Edge(
    #                 kind=_pascal(perm),
    #                 start=EdgePath(value=self.node_id, match_by="id"),
    #                 end=EdgePath(value=self.repository_node_id, match_by="id"),
    #                 properties=EdgeProperties(traversable=False),
    #             )

    @property
    def _bypass_branch_protection_edges(self):
        """Bypasses Merge-Gate Controls (e.g. PR review requirements) <-- done"""
        # TODO Check if enforce_admins should not be checked
        if "bypass_branch_protection" in self.permissions:
            yield Edge(
                kind=ek.BYPASS_BRANCH_PROTECTION,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.repository_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _unprotected_branches_edges(self):
        """Edges from this role to branches that do not have any branch protection rules applied"""
        write_roles = ["write", "maintain", "admin"]
        if self.name in write_roles or self.base_role in write_roles:
            # TODO: Should we check for base role?
            # if self.name in write_roles or self.base_role in write_roles:
            allowed_branches = self._lookup.unprotected_branches(
                self.repository_node_id
            )
            for (target_node_id,) in allowed_branches:
                yield Edge(
                    kind=ek.CAN_WRITE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=target_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _push_protected_branch_bypass_edges(self):
        """Allows pushing to protected branches that restrict pushes (ie. can bypass push restrictions but not other protections)"""

        write_roles = ["write", "maintain", "admin"]
        bypass_roles = ["maintain"]
        push_protected_branch = (
            (
                "push_protected_branch" in self.permissions
                and self.base_role in write_roles
            )
            or self.name in bypass_roles
            or self.base_role in bypass_roles
        )
        if push_protected_branch:
            push_bypass_branches = self._lookup._write_push_restricted_branch_bypass(
                self.repository_node_id
            )
            for (branch_id,) in push_bypass_branches:
                yield Edge(
                    kind=ek.CAN_WRITE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=branch_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _combined_bypass_edges(self):
        """Branches where both merge gate and push gate are blocked, requiring
        bypass_branch_protection (merge gate) + push_protected_branch (push gate)."""
        write_roles = ["write", "maintain", "admin"]
        bypass_roles = ["maintain"]

        has_merge_bypass = (
            "bypass_branch_protection" in self.permissions
            and self.base_role in write_roles
        )
        has_push_bypass = (
            (
                "push_protected_branch" in self.permissions
                and self.base_role in write_roles
            )
            or self.name in bypass_roles
            or self.base_role in bypass_roles
        )

        if has_merge_bypass and has_push_bypass:
            branches = self._lookup._write_combined_bypass(self.repository_node_id)
            for (branch_id,) in branches:
                yield Edge(
                    kind=ek.CAN_WRITE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=branch_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _admin_bypass_edges(self):
        if self.name == "admin" or self.base_role == "admin":
            admin_bypass_branches = self._lookup._write_admin_bypass(
                self.repository_node_id
            )
            for (branch_id,) in admin_bypass_branches:
                yield Edge(
                    kind=ek.CAN_WRITE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=branch_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _branch_protection_bypass_edges(self):
        """Allows pushing to protected branches that restrict pushes (ie. can bypass push restrictions but not other protections)"""

        write_roles = ["write", "maintain", "admin"]
        bypass_branch_protection = (
            "bypass_branch_protection" in self.permissions
            and self.base_role in write_roles
        )

        if bypass_branch_protection:
            protection_bypass_branches = self._lookup._write_branch_protection_bypass(
                self.repository_node_id
            )
            for (branch_id,) in protection_bypass_branches:
                yield Edge(
                    kind=ek.CAN_WRITE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=branch_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _bypass_push_protected_branch_edges(self):
        """Restricts push permissions to protected branches <-- done"""
        # TODO: Check if the base_role can also be maintan or admin
        if "push_protected_branch" in self.permissions:
            yield Edge(
                kind=ek.PUSH_PROTECTED_BRANCH,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.repository_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _can_create_branch_edges(self):
        write_roles = ["write", "maintain", "admin"]
        if self.name in write_roles or self.base_role in write_roles:
            if self._lookup.role_can_create_branch(self.id, self.repository_node_id):
                yield Edge(
                    kind=ek.CAN_CREATE_BRANCH,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=self.repository_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

    @property
    def _can_edit_repo_protection_edges(self):
        if "edit_repo_protections" in self.permissions:
            yield Edge(
                kind=ek.EDIT_REPO_PROTECTIONS,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.repository_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _can_edit_branch_protection_edges(self):
        write_roles = ["write", "maintain", "admin"]
        has_edit_permissions = (
            "edit_repo_protections" in self.permissions
            and self.base_role in write_roles
        )

        if has_edit_permissions or self.name == "admin":
            allowed_branches = self._lookup.branches_with_bpr(self.repository_node_id)
            for (target_node_id,) in allowed_branches:
                yield Edge(
                    kind=ek.CAN_EDIT_PROTECTION,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=target_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def edges(self):
        # # Within-repo base role hierarchy (triage→read, maintain→write, custom→base_role)
        if self.base_role:
            yield Edge(
                kind=ek.HAS_BASE_ROLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(
                    value=f"{self.repository_node_id}_{self.base_role}", match_by="id"
                ),
                properties=EdgeProperties(traversable=True),
            )

        # Can WriteBranch edges
        yield from self._admin_bypass_edges
        yield from self._unprotected_branches_edges
        yield from self._push_protected_branch_bypass_edges
        yield from self._branch_protection_bypass_edges
        yield from self._combined_bypass_edges

        # Other edges
        yield from self._default_edges
        yield from self._bypass_branch_protection_edges
        yield from self._bypass_push_protected_branch_edges
        yield from self._can_create_branch_edges
        yield from self._can_edit_repo_protection_edges
        yield from self._can_edit_branch_protection_edges
