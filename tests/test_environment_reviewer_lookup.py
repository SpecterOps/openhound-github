import duckdb

from openhound_github.lookup import GithubLookup
from openhound_github.transforms import ensure_optional_input_tables


def _lookup() -> GithubLookup:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        """
        CREATE TABLE github.repositories (
            node_id VARCHAR,
            default_branch VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE github.branches (
            id VARCHAR,
            name VARCHAR,
            repository_node_id VARCHAR,
            branch_protection_rule JSON
        );
        CREATE TABLE github.repo_roles (
            id BIGINT,
            name VARCHAR,
            base_role VARCHAR,
            repository_node_id VARCHAR,
            permissions JSON
        );
        CREATE TABLE github.repo_role_assignments (
            node_id VARCHAR,
            assignee_type VARCHAR,
            repo_node_id VARCHAR,
            role_name VARCHAR,
            base_role VARCHAR,
            role_permissions JSON
        );
        CREATE TABLE github.teams (
            id VARCHAR,
            parent_team JSON
        );
        CREATE TABLE github.team_members (
            team_id VARCHAR,
            id VARCHAR
        );
        CREATE TABLE github.users (
            id VARCHAR,
            role VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE github.org_roles (
            name VARCHAR,
            base_role VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE github.org_role_members (
            node_id VARCHAR,
            org_role_name VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE github.org_role_teams (
            node_id VARCHAR,
            org_role_name VARCHAR,
            org_login VARCHAR
        );
        CREATE TABLE github.role_can_create_branch (
            id BIGINT,
            repository_node_id VARCHAR
        );
        CREATE TABLE github.unprotected_branches (
            id VARCHAR,
            repository_node_id VARCHAR
        );
        CREATE TABLE github.branch_bpr (
            id VARCHAR,
            repository_node_id VARCHAR,
            requires_approving_reviews BOOLEAN,
            lock_branch BOOLEAN,
            restricts_pushes BOOLEAN,
            is_admin_enforced BOOLEAN
        );
        CREATE TABLE github.actor_branch_gates (
            actor_id VARCHAR,
            branch_id VARCHAR,
            repository_node_id VARCHAR,
            has_push_allowance BOOLEAN,
            has_pr_allowance BOOLEAN,
            requires_approving_reviews BOOLEAN,
            lock_branch BOOLEAN,
            restricts_pushes BOOLEAN,
            is_admin_enforced BOOLEAN
        );
        """
    )
    connection.execute(
        """
        INSERT INTO github.repositories VALUES ('REPO_1', 'main', 'acme');
        INSERT INTO github.branches VALUES
            ('B_main', 'main', 'REPO_1', NULL),
            ('B_release', 'release', 'REPO_1', '{"id":"BPR_1"}');
        INSERT INTO github.repo_roles VALUES (2, 'write', NULL, 'REPO_1', '[]');
        INSERT INTO github.repo_role_assignments VALUES
            ('TEAM_PARENT', 'team', 'REPO_1', 'write', NULL, '[]');
        INSERT INTO github.teams VALUES
            ('TEAM_CHILD', '{"id":"TEAM_PARENT"}'),
            ('TEAM_PARENT', NULL),
            ('TEAM_ORG_CHILD', '{"id":"TEAM_ORG_PARENT"}'),
            ('TEAM_ORG_PARENT', NULL);
        INSERT INTO github.team_members VALUES ('TEAM_CHILD', 'USER_1');
        INSERT INTO github.team_members VALUES ('TEAM_ORG_CHILD', 'USER_ORG_TEAM');
        INSERT INTO github.users VALUES
            ('USER_MEMBER', 'MEMBER', 'acme'),
            ('USER_ORG_TEAM', 'MEMBER', 'acme');
        INSERT INTO github.org_roles VALUES
            ('members', 'write', 'acme'),
            ('deployers', 'write', 'acme');
        INSERT INTO github.org_role_teams VALUES ('TEAM_ORG_PARENT', 'deployers', 'acme');
        INSERT INTO github.role_can_create_branch VALUES (2, 'REPO_1');
        INSERT INTO github.unprotected_branches VALUES ('B_main', 'REPO_1');
        """
    )
    return GithubLookup(connection)


def test_reviewer_deployment_path_unrolls_user_team_membership_for_branch_creation() -> None:
    lookup = _lookup()

    assert lookup.reviewer_deployment_path(
        "USER_1",
        "user",
        "REPO_1",
        ("B_main",),
        True,
    ) == ("create_branch", None)


def test_reviewer_deployment_path_requires_an_eligible_writable_branch() -> None:
    lookup = _lookup()

    assert (
        lookup.reviewer_deployment_path(
            "USER_1",
            "user",
            "REPO_1",
            ("B_release",),
            False,
        )
        is None
    )


def test_reviewer_deployment_path_unrolls_default_org_role() -> None:
    lookup = _lookup()

    assert lookup.reviewer_deployment_path(
        "USER_MEMBER",
        "user",
        "REPO_1",
        ("B_main",),
        True,
    ) == ("create_branch", None)


def test_reviewer_deployment_path_unrolls_custom_org_role_through_parent_team() -> None:
    lookup = _lookup()

    assert lookup.reviewer_deployment_path(
        "USER_ORG_TEAM",
        "user",
        "REPO_1",
        ("B_main",),
        True,
    ) == ("create_branch", None)


def test_reviewer_deployment_path_preserves_direct_assignment_without_org_roles() -> None:
    lookup = _lookup()
    lookup.client.execute("DROP TABLE github.org_roles")
    lookup.client.execute(
        """
        INSERT INTO github.repo_role_assignments VALUES
            ('USER_DIRECT', 'user', 'REPO_1', 'write', NULL, '[]')
        """
    )
    ensure_optional_input_tables(lookup.client)

    assert lookup.reviewer_deployment_path(
        "USER_DIRECT",
        "user",
        "REPO_1",
        ("B_main",),
        True,
    ) == ("create_branch", None)
