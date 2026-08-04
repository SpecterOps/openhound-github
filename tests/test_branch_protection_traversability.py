from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.branch import Branch
from openhound_github.models.team import Team
from openhound_github.models.user import User


def test_protected_by_edge_is_non_traversable() -> None:
    branch = Branch(
        id="B_1",
        name="main",
        target={"oid": "abc123"},
        branchProtectionRule={"id": "BPR_1"},
        repository_node_id="R_1",
        repository_name="repo",
        org_login="org",
    )
    branch._lookup = MagicMock()

    edge = next(edge for edge in branch.edges if edge.kind == ek.PROTECTED_BY)

    assert edge.properties.traversable is False


def test_user_branch_protection_allowance_edges_are_non_traversable() -> None:
    user = User(
        id="U_1",
        login="alice",
        role="MEMBER",
        org_login="org",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.bypass_pull_request_allowances.return_value = [("BPR_1",)]
    lookup.bypass_push_restrictions.return_value = [("BPR_2",)]
    user._lookup = lookup

    allowance_edges = [
        edge
        for edge in user.edges
        if edge.kind in {ek.BYPASS_PULL_REQUEST_ALLOWANCES, ek.RESTRICTIONS_CAN_PUSH}
    ]

    assert {edge.kind for edge in allowance_edges} == {
        ek.BYPASS_PULL_REQUEST_ALLOWANCES,
        ek.RESTRICTIONS_CAN_PUSH,
    }
    assert all(edge.properties.traversable is False for edge in allowance_edges)


def test_team_branch_protection_allowance_edges_are_non_traversable() -> None:
    team = Team(
        id="T_1",
        name="team",
        slug="team",
        members={"edges": [], "pageInfo": {"endCursor": None, "hasNextPage": False}},
        org_login="org",
    )
    lookup = MagicMock()
    lookup.bypass_pull_request_allowances.return_value = [("BPR_1",)]
    lookup.bypass_push_restrictions.return_value = [("BPR_2",)]
    team._lookup = lookup

    allowance_edges = [
        edge
        for edge in team.edges
        if edge.kind in {ek.BYPASS_PULL_REQUEST_ALLOWANCES, ek.RESTRICTIONS_CAN_PUSH}
    ]

    assert {edge.kind for edge in allowance_edges} == {
        ek.BYPASS_PULL_REQUEST_ALLOWANCES,
        ek.RESTRICTIONS_CAN_PUSH,
    }
    assert all(edge.properties.traversable is False for edge in allowance_edges)
