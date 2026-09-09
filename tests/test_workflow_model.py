import base64
from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.workflow import (
    Workflow,
    resolve_effective_github_token_permissions,
)
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


def _permissions_map(permissions: list[str] | None) -> dict[str, str]:
    assert permissions is not None
    return dict(permission.split(":", 1) for permission in permissions)


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


def test_workflow_job_rows_preserve_workflow_and_job_permission_declarations() -> None:
    workflow = _workflow_from_yaml(
        b"""permissions:
  contents: read
jobs:
  inherited:
    runs-on: ubuntu-latest
  overridden:
    runs-on: ubuntu-latest
    permissions:
      issues: write
  explicit_empty:
    runs-on: ubuntu-latest
    permissions: {}
  read_all:
    runs-on: ubuntu-latest
    permissions: read-all
"""
    )
    workflow.repository_default_workflow_permissions = "read"

    rows = {row["job_key"]: row for row in workflow.workflow_job_rows()}
    workflow._lookup = _org_reference_lookup()

    assert workflow.as_node.properties.workflow_permissions == ["contents:read"]

    assert rows["inherited"]["permissions"] == {"contents": "read"}
    assert rows["inherited"]["job_permissions"] is None
    assert _permissions_map(rows["inherited"]["effective_github_token_permissions"])[
        "contents"
    ] == "read"
    assert _permissions_map(rows["inherited"]["effective_github_token_permissions"])[
        "issues"
    ] == "none"

    assert rows["overridden"]["permissions"] == {"issues": "write"}
    assert rows["overridden"]["job_permissions"] == {"issues": "write"}
    assert _permissions_map(rows["overridden"]["effective_github_token_permissions"])[
        "issues"
    ] == "write"
    assert _permissions_map(rows["overridden"]["effective_github_token_permissions"])[
        "contents"
    ] == "none"

    assert rows["explicit_empty"]["permissions"] == {}
    assert rows["explicit_empty"]["job_permissions"] == {}
    assert set(
        _permissions_map(
            rows["explicit_empty"]["effective_github_token_permissions"]
        ).values()
    ) == {"none"}

    assert rows["read_all"]["permissions"] == "read-all"
    assert rows["read_all"]["job_permissions"] == "read-all"
    assert _permissions_map(rows["read_all"]["effective_github_token_permissions"])[
        "contents"
    ] == "read"
    assert _permissions_map(rows["read_all"]["effective_github_token_permissions"])[
        "id-token"
    ] == "none"

    job = WorkflowJob.model_validate(rows["explicit_empty"])
    job._lookup = _org_reference_lookup()

    assert job.permissions == []
    assert job.job_permissions == []
    assert set(_permissions_map(job.effective_github_token_permissions).values()) == {
        "none"
    }
    assert job.as_node.properties.job_permissions == []
    assert set(
        _permissions_map(
            job.as_node.properties.effective_github_token_permissions
        ).values()
    ) == {"none"}


def test_workflow_job_rows_preserve_job_secret_reference_contexts() -> None:
    workflow = _workflow_from_yaml(
        b"""jobs:
  build:
    runs-on: ubuntu-latest
    env:
      DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
    secrets:
      forwarded_token: ${{ secrets.FORWARDED_TOKEN }}
"""
    )

    row = workflow.workflow_job_rows()[0]

    assert row["secret_references"] == [
        {"name": "FORWARDED_TOKEN", "context": "secrets:forwarded_token"},
        {"name": "DEPLOY_TOKEN", "context": "env:DEPLOY_TOKEN"},
    ]


def test_effective_github_token_permissions_use_repository_default_when_undeclared() -> None:
    permissions = _permissions_map(
        resolve_effective_github_token_permissions("read", None, None)
    )

    assert permissions["contents"] == "read"
    assert permissions["packages"] == "read"
    assert permissions["issues"] == "none"
    assert permissions["id-token"] == "none"


def test_effective_github_token_permissions_do_not_inherit_id_token_from_write_default() -> None:
    permissions = _permissions_map(
        resolve_effective_github_token_permissions("write", None, None)
    )

    assert permissions["contents"] == "write"
    assert permissions["pull-requests"] == "write"
    assert permissions["id-token"] == "none"


def test_effective_github_token_permissions_allow_explicit_elevation_from_default() -> None:
    permissions = _permissions_map(
        resolve_effective_github_token_permissions(
            "read",
            {"contents": "read"},
            {"issues": "write"},
        )
    )

    assert permissions["issues"] == "write"
    assert permissions["contents"] == "none"
    assert permissions["packages"] == "none"


def test_effective_github_token_permissions_expand_write_all() -> None:
    permissions = _permissions_map(
        resolve_effective_github_token_permissions("read", "write-all", None)
    )

    assert permissions["contents"] == "write"
    assert permissions["id-token"] == "write"
    assert permissions["models"] == "read"
    assert permissions["vulnerability-alerts"] == "read"


def test_job_permissions_override_workflow_id_token_permission() -> None:
    workflow = _workflow_from_yaml(
        b"""permissions:
  id-token: write
  contents: read
jobs:
  inherited:
    runs-on: ubuntu-latest
  overridden:
    runs-on: ubuntu-latest
    permissions:
      contents: read
"""
    )
    workflow.repository_default_workflow_permissions = "read"

    rows = {row["job_key"]: row for row in workflow.workflow_job_rows()}

    inherited = _permissions_map(
        rows["inherited"]["effective_github_token_permissions"]
    )
    overridden = _permissions_map(
        rows["overridden"]["effective_github_token_permissions"]
    )

    assert inherited["id-token"] == "write"
    assert inherited["contents"] == "read"
    assert overridden["id-token"] == "none"
    assert overridden["contents"] == "read"


def test_workflow_job_node_recalculates_effective_permissions_during_conversion() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        effective_github_token_permissions=["id-token:write"],
    )
    lookup = _org_reference_lookup()
    lookup.repository_workflow_permissions.return_value = ("write", False)
    job._lookup = lookup

    permissions = _permissions_map(
        job.as_node.properties.effective_github_token_permissions
    )

    assert permissions["contents"] == "write"
    assert permissions["id-token"] == "none"


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


def test_workflow_job_node_exposes_accessible_secret_query() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
    )
    job._lookup = _org_reference_lookup()

    assert job.as_node.properties.query_accessible_secrets == (
        "MATCH p=(:GH_WorkflowJob {node_id:'JOB_1'})"
        "-[:GH_CanAccessSecret]->(:GH_Secret) RETURN p"
    )


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


def test_workflow_job_emits_can_intercept_job_edges_for_interceptable_runner_matches() -> None:
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
    lookup.workflow_job_interceptable_runner_node_ids.return_value = [
        "REPO_1_runner_1",
        "ORG_1_runner_2",
    ]
    job._lookup = lookup

    edges = list(job._can_intercept_job_edges)

    assert [(edge.kind, edge.start.value, edge.end.value) for edge in edges] == [
        (ek.CAN_INTERCEPT_JOB, "REPO_1_runner_1", "JOB_1"),
        (ek.CAN_INTERCEPT_JOB, "ORG_1_runner_2", "JOB_1"),
    ]
    assert all(edge.properties.traversable is True for edge in edges)
    assert all(edge.properties.composed is True for edge in edges)
    assert edges[0].properties.query_composition == (
        "MATCH p=(:GH_WorkflowJob {node_id:'JOB_1'})"
        "-[:GH_RunsOn]->(:GH_Runner {node_id:'REPO_1_runner_1'}) RETURN p"
    )
    lookup.workflow_job_interceptable_runner_node_ids.assert_called_once_with(
        "REPO_1",
        "github",
        None,
        ("self-hosted", "linux", "x64"),
    )


def test_workflow_job_emits_can_access_secret_edges_for_step_references() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        environment="prod",
    )
    lookup = _org_reference_lookup()
    lookup.workflow_step_secret_reference_names.return_value = [
        "REPO_TOKEN",
        "ORG_TOKEN",
        "ENV_TOKEN",
    ]
    lookup.repo_secret.side_effect = lambda name, _repo_id: (
        (name,) if name == "REPO_TOKEN" else None
    )
    lookup.org_secret.side_effect = lambda name, _org_login: (
        (name,) if name == "ORG_TOKEN" else None
    )
    lookup.environment_secret_for_environment.side_effect = (
        lambda name, _repo_id, _environment: (name,) if name == "ENV_TOKEN" else None
    )
    job._lookup = lookup

    edges = list(job._can_access_secret_edges)

    assert [edge.kind for edge in edges] == [
        ek.CAN_ACCESS_SECRET,
        ek.CAN_ACCESS_SECRET,
        ek.CAN_ACCESS_SECRET,
    ]
    assert [edge.end.kind for edge in edges] == [
        nk.REPO_SECRET,
        nk.ORG_SECRET,
        nk.ENVIRONMENT_SECRET,
    ]
    assert all(edge.properties.traversable is True for edge in edges)
    assert all(edge.properties.composed is True for edge in edges)
    assert "GH_Contains" in edges[0].properties.query_composition
    assert "GH_UsesSecret" in edges[0].properties.query_composition


def test_workflow_job_emits_can_request_oidc_token_for_environment_without_oidc_step() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="deploy",
        job_key="deploy",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        environment="prod",
        permissions={"id-token": "write"},
    )
    lookup = _org_reference_lookup()
    lookup.environment.return_value = "prod"
    job._lookup = lookup

    environment_edges = list(job._environment_edges)
    edges = list(job._can_request_oidc_token_for_edges)

    assert len(environment_edges) == 1
    assert _matcher_values(environment_edges[0]) == {
        "repository_id": "REPO_1",
        "name": "prod",
    }
    assert len(edges) == 1
    assert edges[0].kind == ek.CAN_REQUEST_OIDC_TOKEN_FOR
    assert edges[0].start.value == "JOB_1"
    assert edges[0].end.kind == nk.ENVIRONMENT
    assert _matcher_values(edges[0]) == {
        "repository_id": "REPO_1",
        "name": "prod",
    }
    assert edges[0].properties.traversable is True
    assert edges[0].properties.composed is True
    assert edges[0].properties.query_composition == (
        "MATCH p=(job:GH_WorkflowJob {node_id:'JOB_1'})"
        "-[:GH_DeploysTo]->(:GH_Environment) "
        "WHERE 'id-token:write' IN job.effective_github_token_permissions "
        "RETURN p"
    )


def test_workflow_job_can_request_oidc_token_for_requires_permission_and_environment() -> None:
    no_permission = WorkflowJob(
        node_id="JOB_NO_PERMISSION",
        name="deploy",
        job_key="deploy",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        environment="prod",
        permissions={"contents": "read"},
    )
    no_environment = WorkflowJob(
        node_id="JOB_NO_ENVIRONMENT",
        name="deploy",
        job_key="deploy",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        permissions={"id-token": "write"},
    )
    lookup = _org_reference_lookup()
    lookup.environment.return_value = "prod"
    no_permission._lookup = lookup
    no_environment._lookup = lookup

    assert list(no_permission._can_request_oidc_token_for_edges) == []
    assert list(no_environment._can_request_oidc_token_for_edges) == []


def test_workflow_job_can_request_oidc_token_for_edges_are_per_job_and_idempotent() -> None:
    jobs = [
        WorkflowJob(
            node_id="JOB_1",
            name="deploy",
            job_key="deploy",
            workflow_node_id="WORKFLOW_1",
            repository_name="repo",
            repository_node_id="REPO_1",
            org_login="github",
            environment="prod",
            permissions={"id-token": "write"},
        ),
        WorkflowJob(
            node_id="JOB_2",
            name="publish",
            job_key="publish",
            workflow_node_id="WORKFLOW_1",
            repository_name="repo",
            repository_node_id="REPO_1",
            org_login="github",
            environment="prod",
            permissions={"id-token": "write"},
        ),
        WorkflowJob(
            node_id="JOB_3",
            name="build",
            job_key="build",
            workflow_node_id="WORKFLOW_1",
            repository_name="repo",
            repository_node_id="REPO_1",
            org_login="github",
            environment="prod",
            permissions={"contents": "read"},
        ),
    ]
    lookup = _org_reference_lookup()
    lookup.environment.return_value = "prod"
    for job in jobs:
        job._lookup = lookup

    edges = [
        edge
        for job in jobs
        for edge in job.edges
        if edge.kind == ek.CAN_REQUEST_OIDC_TOKEN_FOR
    ]

    assert [(edge.start.value, _matcher_values(edge)) for edge in edges] == [
        ("JOB_1", {"repository_id": "REPO_1", "name": "prod"}),
        ("JOB_2", {"repository_id": "REPO_1", "name": "prod"}),
    ]
    assert len(list(jobs[0]._can_request_oidc_token_for_edges)) == 1


def test_workflow_job_can_access_secret_edges_deduplicate_step_references() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
    )
    lookup = _org_reference_lookup()
    lookup.workflow_step_secret_reference_names.return_value = [
        "DEPLOY_TOKEN",
        "deploy_token",
    ]
    lookup.org_secret.return_value = ("DEPLOY_TOKEN",)
    job._lookup = lookup

    edges = list(job._can_access_secret_edges)

    assert len(edges) == 1
    assert edges[0].end.kind == nk.ORG_SECRET
    assert _matcher_values(edges[0]) == {
        "name": "DEPLOY_TOKEN",
        "environmentid": ORG_NODE_ID,
    }


def test_workflow_job_job_level_secret_reference_alone_does_not_emit_can_access_secret() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        secret_references=[
            {"name": "FORWARDED_TOKEN", "context": "secrets:forwarded_token"}
        ],
    )
    lookup = _org_reference_lookup()
    lookup.workflow_step_secret_reference_names.return_value = []
    job._lookup = lookup

    assert list(job._can_access_secret_edges) == []


def test_workflow_job_job_env_secret_reference_emits_can_access_secret() -> None:
    job = WorkflowJob(
        node_id="JOB_1",
        name="build",
        job_key="build",
        workflow_node_id="WORKFLOW_1",
        repository_name="repo",
        repository_node_id="REPO_1",
        org_login="github",
        secret_references=[{"name": "DEPLOY_TOKEN", "context": "env:DEPLOY_TOKEN"}],
    )
    lookup = _org_reference_lookup()
    lookup.workflow_step_secret_reference_names.return_value = []
    lookup.org_secret.return_value = ("DEPLOY_TOKEN",)
    job._lookup = lookup

    edges = list(job._can_access_secret_edges)

    assert len(edges) == 1
    assert edges[0].end.kind == nk.ORG_SECRET
    assert edges[0].properties.query_composition == (
        "MATCH p=(:GH_WorkflowJob {node_id:'JOB_1'})"
        "-[:GH_UsesSecret]->(:GH_OrgSecret "
        "{name:'DEPLOY_TOKEN', environmentid:'MDEyOk9yZ2FuaXphdGlvbjE='}) RETURN p"
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
    assert list(job._can_intercept_job_edges) == []
    lookup.workflow_job_interceptable_runner_node_ids.assert_not_called()


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
    lookup.repository_workflow_permissions.return_value = None
    lookup.environment.return_value = None
    lookup.workflow_step_secret_reference_names.return_value = []
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
