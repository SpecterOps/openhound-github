import base64
from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.workflow import Workflow
from openhound_github.models.workflow_job import WorkflowJob
from openhound_github.models.workflow_step import WorkflowStep


ORG_NODE_ID = "MDEyOk9yZ2FuaXphdGlvbjE="


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


def _org_reference_lookup() -> MagicMock:
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = ORG_NODE_ID
    lookup.repo_secret.return_value = None
    lookup.org_secret.return_value = ("DEPLOY_TOKEN",)
    lookup.repo_variable.return_value = None
    lookup.org_variable.return_value = ("DEPLOY_ENV",)
    return lookup


def _matcher_values(edge) -> dict[str, str | None]:
    return {matcher.key: matcher.value for matcher in edge.end.property_matchers}


def test_workflow_job_org_reference_edges_preserve_org_node_id_case() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        secret_references=[{"name": "DEPLOY_TOKEN"}],
        variable_references=[{"name": "DEPLOY_ENV"}],
    )
    job._lookup = _org_reference_lookup()

    secret_edge = next(
        edge for edge in job._uses_secret_edges if edge.end.kind == nk.ORG_SECRET
    )
    variable_edge = next(
        edge for edge in job._uses_variable_edges if edge.end.kind == nk.ORG_VARIABLE
    )

    assert _matcher_values(secret_edge) == {
        "name": "DEPLOY_TOKEN",
        "environmentid": ORG_NODE_ID,
    }
    assert _matcher_values(variable_edge) == {
        "name": "DEPLOY_ENV",
        "environmentid": ORG_NODE_ID,
    }


def test_workflow_step_org_reference_edges_preserve_org_node_id_case() -> None:
    step = WorkflowStep(
        node_id="STEP_1",
        name="deploy",
        step_index=0,
        type="run",
        job_node_id="JOB_1",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        secret_references=[{"name": "DEPLOY_TOKEN"}],
        variable_references=[{"name": "DEPLOY_ENV"}],
    )
    step._lookup = _org_reference_lookup()

    secret_edge = next(
        edge for edge in step._uses_secret_edges if edge.end.kind == nk.ORG_SECRET
    )
    variable_edge = next(
        edge for edge in step._uses_variable_edges if edge.end.kind == nk.ORG_VARIABLE
    )

    assert _matcher_values(secret_edge) == {
        "name": "DEPLOY_TOKEN",
        "environmentid": ORG_NODE_ID,
    }
    assert _matcher_values(variable_edge) == {
        "name": "DEPLOY_ENV",
        "environmentid": ORG_NODE_ID,
    }
