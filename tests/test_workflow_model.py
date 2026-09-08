import base64
from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.workflow import Workflow
from openhound_github.models.workflow_job import WorkflowJob
from openhound_github.models.workflow_step import WorkflowStep


ORG_NODE_ID = "MDEyOk9yZ2FuaXphdGlvbjE="


def _workflow_from_yaml(contents: bytes) -> Workflow:
    return Workflow(
        id=1,
        node_id="W_1",
        name="workflow.yml",
        path=".github/workflows/workflow.yml",
        state="active",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        url="https://api.github.test/repos/org/repo/actions/workflows/1",
        contents=base64.b64encode(contents).decode(),
        org_login="org",
        repository_name="repo",
        repository_node_id="R_1",
    )


def _make_pwn_request_workflow() -> Workflow:
    workflow = _workflow_from_yaml(
        b"""on:
  pull_request_target:
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
"""
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


def test_workflow_job_rows_preserve_runs_on_selector_shape() -> None:
    workflow = _workflow_from_yaml(
        b"""jobs:
  plain:
    runs-on: self-hosted
  labels:
    runs-on: [self-hosted, linux, x64]
  group_only:
    runs-on:
      group: prod-runners
  group_and_label:
    runs-on:
      group: prod-runners
      labels: linux-x64
  dynamic:
    runs-on: "${{ matrix.runner }}"
"""
    )

    rows = {row["job_key"]: row for row in workflow.workflow_job_rows()}

    assert rows["plain"]["runs_on_labels"] == ["self-hosted"]
    assert rows["plain"]["runs_on_group"] is None
    assert rows["plain"]["runs_on_is_dynamic"] is False

    assert rows["labels"]["runs_on_labels"] == ["self-hosted", "linux", "x64"]
    assert rows["labels"]["runs_on_group"] is None
    assert rows["labels"]["runs_on_is_dynamic"] is False

    assert rows["group_only"]["runs_on_labels"] is None
    assert rows["group_only"]["runs_on_group"] == "prod-runners"
    assert rows["group_only"]["runs_on_is_dynamic"] is False

    assert rows["group_and_label"]["runs_on_labels"] == ["linux-x64"]
    assert rows["group_and_label"]["runs_on_group"] == "prod-runners"
    assert rows["group_and_label"]["runs_on_is_dynamic"] is False

    assert rows["dynamic"]["runs_on_labels"] == ["${{ matrix.runner }}"]
    assert rows["dynamic"]["runs_on_group"] is None
    assert rows["dynamic"]["runs_on_is_dynamic"] is True


def test_workflow_job_group_selector_counts_as_self_hosted() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        runs_on={"group": "prod-runners"},
    )
    job._lookup = _org_reference_lookup()

    assert job.runs_on is None
    assert job.runs_on_group == "prod-runners"
    assert job.runs_on_labels is None
    assert job.runs_on_is_dynamic is False
    assert job.is_self_hosted is True
    assert job.as_node.properties.is_self_hosted is True


def test_workflow_job_uppercase_self_hosted_label_counts_as_self_hosted() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        runs_on=["SELF-HOSTED", "Linux", "X64"],
    )
    job._lookup = _org_reference_lookup()

    assert job.runs_on_labels == ["SELF-HOSTED", "Linux", "X64"]
    assert job.is_self_hosted is True
    assert job.as_node.properties.is_self_hosted is True


def test_workflow_job_emits_runs_on_edges_for_static_selector_matches() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        runs_on=["self-hosted", "linux", "x64"],
    )
    lookup = _org_reference_lookup()
    lookup.workflow_job_runner_node_ids.return_value = [
        "REPO_1_runner_1",
        "ORG_1_runner_2",
    ]
    job._lookup = lookup

    edges = list(job._runs_on_edges)

    assert [(edge.kind, edge.start.value, edge.end.value) for edge in edges] == [
        (ek.RUNS_ON, "JOB_1", "REPO_1_runner_1"),
        (ek.RUNS_ON, "JOB_1", "ORG_1_runner_2"),
    ]
    assert all(edge.properties.traversable is False for edge in edges)
    lookup.workflow_job_runner_node_ids.assert_called_once_with(
        "REPO_1",
        "github",
        None,
        ("self-hosted", "linux", "x64"),
    )


def test_workflow_job_dynamic_runs_on_selector_emits_no_edge() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        runs_on="${{ matrix.runner }}",
    )
    lookup = _org_reference_lookup()
    job._lookup = lookup

    assert list(job._runs_on_edges) == []
    lookup.workflow_job_runner_node_ids.assert_not_called()


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
