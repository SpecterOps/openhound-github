from openhound.core.asset import BaseAsset, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import Field

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

TEAM_PERMISSION_MAP: dict[str, str] = {
    "admin": "admin",
    "maintain": "maintain",
    "push": "write",
    "triage": "triage",
    "pull": "read",
}


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.REPO_ROLE,
            kind=ek.HAS_ROLE,
            description="User has repo role",
            traversable=True,
        ),
        EdgeDef(
            start=nk.TEAM,
            end=nk.REPO_ROLE,
            kind=ek.HAS_ROLE,
            description="Team has repo role",
            traversable=True,
        ),
        EdgeDef(
            start=nk.USER,
            end=nk.BRANCH,
            kind=ek.CAN_WRITE_BRANCH,
            description="User can push commits to this branch via actor-level bypass allowances",
            traversable=False,
        ),
        EdgeDef(
            start=nk.TEAM,
            end=nk.BRANCH,
            kind=ek.CAN_WRITE_BRANCH,
            description="Team can push commits to this branch via actor-level bypass allowances",
            traversable=False,
        ),
    ],
)
class RepoRoleAssignment(BaseAsset):
    login: str | None = None
    id: int
    node_id: str
    type: str
    permissions: dict | None = None
    role_name: str | None = None

    # Additional
    org_login: str
    assignee_type: str  # "user" or "team"
    repo_node_id: str
    repo_name: str
    base_role: str | None = None
    role_permissions: list[str] = Field(default_factory=list)

    @property
    def as_node(self) -> None:
        return None

    @property
    def _bypass_edges(self):
        write_roles = ["write", "maintain", "admin"]
        bypass_roles = ["maintain"]

        has_write_access = (
            self.role_name in write_roles or self.base_role in write_roles
        )
        if not has_write_access:
            return

        # Admin covers everything at role level already
        if self.role_name == "admin" or self.base_role == "admin":
            return

        has_push_protected = bool(
            (self.role_permissions and "push_protected_branch" in self.role_permissions)
            or self.role_name in bypass_roles
            or self.base_role in bypass_roles
        )
        has_bypass_branch = bool(
            self.role_permissions
            and "bypass_branch_protection" in self.role_permissions
        )

        # We can skip processing if the role already has the necessary permissions
        if has_push_protected and has_bypass_branch:
            return

        branches = self._lookup.actor_gate_bypass(
            self.node_id,
            self.repo_node_id,
            has_bypass_branch,
            has_push_protected,
        )
        for (branch_id,) in branches:
            yield Edge(
                kind=ek.CAN_WRITE_BRANCH,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=branch_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def edges(self):
        # TODO: CHeck if edge goes actor → role node (not actor → repo).
        if self.role_name:
            role_node_id = f"{self.repo_node_id}_{self.role_name}"
            yield Edge(
                kind=ek.HAS_ROLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=role_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

        yield from self._bypass_edges
