import duckdb

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.lookup import GithubLookup
from openhound_github.models.runner import (
    EnterpriseRunnerGroupMembership,
    OrgRunnerGroup,
    OrgRunnerGroupAccess,
)
from openhound_github.models.workflow_job import WorkflowJob
from openhound_github.models.workflow_step import WorkflowStep
from openhound_github.transforms import ensure_optional_input_tables


def _cross_org_enterprise_runner_lookup() -> GithubLookup:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.organizations (login VARCHAR, node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.repositories "
        "(node_id VARCHAR, org_login VARCHAR, visibility VARCHAR, actions_enabled BOOLEAN)"
    )
    connection.execute(
        "CREATE TABLE github.branches (id VARCHAR, repository_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.repo_runners "
        "(id BIGINT, labels JSON, ephemeral BOOLEAN, repository_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.org_runners "
        "(id BIGINT, labels JSON, ephemeral BOOLEAN, org_login VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.org_runner_group_access "
        "(runner_group_id BIGINT, runner_group_name VARCHAR, "
        "runner_group_visibility VARCHAR, allows_public_repositories BOOLEAN, "
        "restricted_to_workflows BOOLEAN, inherited BOOLEAN, "
        "accessible_repo_node_ids JSON, org_login VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.org_runner_group_memberships "
        "(runner_group_id BIGINT, runner_id BIGINT, org_login VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_organizations "
        "(id VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_groups "
        "(id BIGINT, name VARCHAR, visibility VARCHAR, "
        "restricted_to_workflows BOOLEAN, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_organizations "
        "(node_id VARCHAR, runner_group_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_memberships "
        "(runner_group_id BIGINT, runner_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runners "
        "(id BIGINT, labels JSON, ephemeral BOOLEAN, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.workflow_steps "
        "(job_node_id VARCHAR, secret_references JSON)"
    )
    connection.execute(
        "CREATE TABLE github.repository_secrets "
        "(name VARCHAR, repository_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.organization_secrets (name VARCHAR, org_login VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.environment_secrets "
        "(name VARCHAR, repository_node_id VARCHAR, environment_name VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.environments "
        "(name VARCHAR, repository_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.organizations VALUES "
        "('attacker', 'ORG_A'), ('victim', 'ORG_B')"
    )
    connection.execute(
        "INSERT INTO github.repositories VALUES "
        "('REPO_A', 'attacker', 'private', true), "
        "('REPO_B', 'victim', 'private', true)"
    )
    connection.execute(
        "INSERT INTO github.org_runner_group_access VALUES "
        "(4, 'enterprise-prod', 'selected', true, false, true, '[\"REPO_A\"]', 'attacker'), "
        "(4, 'enterprise-prod', 'selected', true, false, true, '[\"REPO_B\"]', 'victim')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES "
        "('ORG_A', 'ENT_1'), ('ORG_B', 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_groups VALUES "
        "(4, 'enterprise-prod', 'selected', false, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_group_organizations VALUES "
        "('ORG_A', 4, 'ENT_1'), ('ORG_B', 4, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_group_memberships VALUES "
        "(4, 31, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runners VALUES "
        "(31, '[{\"name\":\"self-hosted\"},{\"name\":\"Linux\"}]', false, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.workflow_steps VALUES "
        "('JOB_B', '[{\"name\":\"DEPLOY_TOKEN\",\"context\":\"run\"}]')"
    )
    connection.execute(
        "INSERT INTO github.repository_secrets VALUES ('DEPLOY_TOKEN', 'REPO_B')"
    )
    connection.execute(
        "INSERT INTO github.environments VALUES ('prod', 'REPO_B')"
    )
    return GithubLookup(connection)


def _find_edge(edges, kind: str, start: str, end: str | None = None):
    return next(
        edge
        for edge in edges
        if edge.kind == kind
        and edge.start.value == start
        and (end is None or getattr(edge.end, "value", None) == end)
    )


def test_cross_org_enterprise_runner_interception_path_is_traversable() -> None:
    lookup = _cross_org_enterprise_runner_lookup()

    attacker_access = OrgRunnerGroupAccess(
        runner_group_id=4,
        runner_group_name="enterprise-prod",
        runner_group_visibility="selected",
        restricted_to_workflows=False,
        inherited=True,
        accessible_repo_node_ids=["REPO_A"],
        org_login="attacker",
    )
    attacker_access._lookup = lookup
    attacker_group = OrgRunnerGroup(
        id=4,
        name="enterprise-prod",
        visibility="selected",
        inherited=True,
        org_login="attacker",
    )
    attacker_group._lookup = lookup
    membership = EnterpriseRunnerGroupMembership(
        runner_group_id=4,
        runner_id=31,
        enterprise_node_id="ENT_1",
        enterprise_slug="enterprise",
    )
    victim_job = WorkflowJob(
        node_id="JOB_B",
        name="victim\\deploy",
        job_key="deploy",
        workflow_node_id="WORKFLOW_B",
        repository_name="victim-repo",
        repository_node_id="REPO_B",
        org_login="victim",
        runs_on={"group": "enterprise-prod", "labels": ["self-hosted", "linux"]},
        environment="prod",
        permissions={"id-token": "write"},
    )
    victim_job._lookup = lookup
    victim_step = WorkflowStep(
        node_id="STEP_B",
        name="deploy",
        step_index=0,
        type="run",
        job_node_id="JOB_B",
        workflow_node_id="WORKFLOW_B",
        repository_name="victim-repo",
        repository_node_id="REPO_B",
        org_login="victim",
        secret_references=[{"name": "DEPLOY_TOKEN", "context": "run"}],
    )
    victim_step._lookup = lookup

    access_edges = list(attacker_access.edges)
    group_edges = list(attacker_group.edges)
    membership_edges = list(membership.edges)
    job_edges = list(victim_job.edges)
    step_edges = list(victim_step.edges)

    can_use = _find_edge(
        access_edges, ek.CAN_USE_RUNNER, "REPO_A", "ORG_A_runner_group_4"
    )
    inherited_from = _find_edge(
        group_edges,
        ek.INHERITED_FROM,
        "ORG_A_runner_group_4",
        "ENT_1_runner_group_4",
    )
    has_runner = _find_edge(
        membership_edges, ek.HAS_RUNNER, "ENT_1_runner_group_4", "ENT_1_runner_31"
    )
    runs_on = _find_edge(job_edges, ek.RUNS_ON, "JOB_B", "ENT_1_runner_31")
    can_intercept = _find_edge(
        job_edges, ek.CAN_INTERCEPT_JOB, "ENT_1_runner_31", "JOB_B"
    )
    contains_step = _find_edge(job_edges + step_edges, ek.CONTAINS, "JOB_B", "STEP_B")
    uses_secret = _find_edge(step_edges, ek.USES_SECRET, "STEP_B")
    can_access_secret = _find_edge(job_edges, ek.CAN_ACCESS_SECRET, "JOB_B")
    can_request_oidc_token = _find_edge(
        job_edges, ek.CAN_REQUEST_OIDC_TOKEN_FOR, "JOB_B"
    )

    assert [
        edge.properties.traversable
        for edge in [
            can_use,
            inherited_from,
            has_runner,
            can_intercept,
            can_access_secret,
            can_request_oidc_token,
        ]
    ] == [True, True, True, True, True, True]
    assert runs_on.properties.traversable is False
    assert contains_step.properties.traversable is False
    assert uses_secret.properties.traversable is False
    assert uses_secret.end.kind == nk.REPO_SECRET
    assert can_access_secret.end.kind == nk.REPO_SECRET
    assert {
        matcher.key: matcher.value
        for matcher in can_access_secret.end.property_matchers
    } == {
        "name": "DEPLOY_TOKEN",
        "repository_id": "REPO_B",
    }
    assert can_request_oidc_token.end.kind == nk.ENVIRONMENT
    assert {
        matcher.key: matcher.value
        for matcher in can_request_oidc_token.end.property_matchers
    } == {
        "name": "PROD",
        "repository_id": "REPO_B",
    }


def test_inherited_runner_lookup_survives_upgraded_enterprise_runner_group_stub() -> None:
    lookup = _cross_org_enterprise_runner_lookup()
    lookup.client.execute("DROP TABLE github.enterprise_runner_groups")
    lookup.client.execute(
        "CREATE TABLE github.enterprise_runner_groups "
        "(id BIGINT, name VARCHAR, visibility VARCHAR, enterprise_node_id VARCHAR)"
    )

    ensure_optional_input_tables(lookup.client)
    lookup.client.execute(
        "INSERT INTO github.enterprise_runner_groups "
        "(id, name, visibility, restricted_to_workflows, enterprise_node_id) "
        "VALUES (4, 'enterprise-prod', 'selected', false, 'ENT_1')"
    )

    job = WorkflowJob(
        node_id="JOB_B",
        name="victim\\deploy",
        job_key="deploy",
        workflow_node_id="WORKFLOW_B",
        repository_name="victim-repo",
        repository_node_id="REPO_B",
        org_login="victim",
        runs_on={"group": "enterprise-prod", "labels": ["self-hosted", "linux"]},
    )
    job._lookup = lookup

    edges = list(job.edges)

    _find_edge(edges, ek.RUNS_ON, "JOB_B", "ENT_1_runner_31")
    _find_edge(edges, ek.CAN_INTERCEPT_JOB, "ENT_1_runner_31", "JOB_B")
