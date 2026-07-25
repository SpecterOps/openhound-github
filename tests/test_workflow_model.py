import base64
from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.workflow import Workflow


def _make_pwn_request_workflow() -> Workflow:
    contents = base64.b64encode(
        b"""on:
  pull_request_target:
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
"""
    ).decode()
    workflow = Workflow(
        id=1,
        node_id="W_1",
        name="pr.yml",
        path=".github/workflows/pr.yml",
        state="active",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        url="https://api.github.test/repos/org/repo/actions/workflows/1",
        contents=contents,
        org_login="org",
        repository_name="repo",
        repository_node_id="R_1",
    )
    lookup = MagicMock()
    lookup.repository_allow_forking.return_value = ("public", True)
    lookup.repo_role_node_ids_with_read_repo_contents.return_value = [
        ("ROLE_1",),
        ("ROLE_2",),
    ]
    lookup.branches_for_repository.return_value = [
        ("B_main", "main", False),
        ("B_release", "release/v1", True),
    ]
    workflow._lookup = lookup
    return workflow


def test_pwn_request_edges_support_branch_lookup_protection_flag() -> None:
    workflow = _make_pwn_request_workflow()

    edges = [
        edge for edge in workflow._can_pwn_request_edges if edge.kind == ek.CAN_PWN_REQUEST
    ]

    assert {(edge.start.value, edge.end.value) for edge in edges} == {
        ("ROLE_1", "R_1"),
        ("ROLE_1", "B_main"),
        ("ROLE_1", "B_release"),
        ("ROLE_2", "R_1"),
        ("ROLE_2", "B_main"),
        ("ROLE_2", "B_release"),
    }
