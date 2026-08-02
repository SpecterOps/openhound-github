import duckdb
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.repo_role_assignment import RepoRoleAssignment
from openhound_github.models.repository_role import RepoRole


def _make_repo_role() -> RepoRole:
    role = RepoRole(
        id=1,
        name="admin",
        permissions=[],
        org_login="org",
        type="default",
        repository_node_id="R_1",
        repository_name="repo",
        repository_full_name="org/repo",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.unprotected_branches.return_value = [("B_feature",)]
    lookup._write_admin_bypass.return_value = [("B_protected",)]
    lookup.role_can_create_branch.return_value = "R_1"
    lookup.branches_with_bpr.return_value = [("B_protected",)]
    role._lookup = lookup
    return role


def test_repository_default_branch_collected_requires_default_branch_row() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.repositories (node_id VARCHAR, default_branch VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.branches (id VARCHAR, name VARCHAR, repository_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.repositories VALUES ('R_1', 'main'), ('R_2', 'main'), ('R_3', NULL)"
    )
    connection.execute(
        "INSERT INTO github.branches VALUES ('B_1', 'main', 'R_1'), ('B_2', 'feature', 'R_2')"
    )

    lookup = GithubLookup(connection)

    assert lookup.repository_default_branch_collected("R_1") is True
    assert lookup.repository_default_branch_collected("R_2") is False
    assert lookup.repository_default_branch_collected("R_3") is False


def test_repo_role_branch_edges_require_collected_default_branch() -> None:
    role = _make_repo_role()
    role._lookup.repository_default_branch_collected.return_value = False

    edges = list(role.edges)

    assert not any(
        edge.kind in {ek.CAN_WRITE_BRANCH, ek.CAN_CREATE_BRANCH, ek.CAN_EDIT_PROTECTION}
        for edge in edges
    )
    role._lookup.unprotected_branches.assert_not_called()
    role._lookup._write_admin_bypass.assert_not_called()
    role._lookup.role_can_create_branch.assert_not_called()
    role._lookup.branches_with_bpr.assert_not_called()


def test_repo_role_branch_edges_emit_after_default_branch_is_collected() -> None:
    role = _make_repo_role()
    role._lookup.repository_default_branch_collected.return_value = True

    edges = list(role.edges)

    assert {edge.kind for edge in edges} >= {
        ek.CAN_WRITE_BRANCH,
        ek.CAN_CREATE_BRANCH,
        ek.CAN_EDIT_PROTECTION,
    }


def test_actor_branch_write_edges_require_collected_default_branch() -> None:
    assignment = RepoRoleAssignment(
        id=1,
        node_id="U_1",
        type="User",
        org_login="org",
        assignee_type="user",
        repo_node_id="R_1",
        repo_name="repo",
        role_name="write",
        base_role="write",
    )
    lookup = MagicMock()
    lookup.repository_default_branch_collected.return_value = False
    lookup.actor_gate_bypass.return_value = [("B_1",)]
    assignment._lookup = lookup

    edges = list(assignment.edges)

    assert not any(edge.kind == ek.CAN_WRITE_BRANCH for edge in edges)
    lookup.actor_gate_bypass.assert_not_called()
