import json

import duckdb
import pytest

from openhound_github.branch_creation import branch_creation_restriction
from openhound_github.transforms import (
    branch_creation_eligibility,
    ensure_app_installation_input_tables,
    ensure_optional_input_tables,
    role_can_create_branch,
)


@pytest.mark.parametrize(
    "pattern",
    [
        "main",
        "release",
        "release/*",
        "release/**/*",
        "team/[a-z]*",
        "*protections_test*",
        "*release*",
        "release-*",
        "**/release/*",
    ],
)
def test_named_restrictions_leave_freely_named_branches_available(pattern):
    assert branch_creation_restriction(pattern, True, True) is None


@pytest.mark.parametrize("pattern", ["*", "**", "**/*"])
def test_broad_creation_restrictions_require_actor_evaluation(pattern):
    assert (
        branch_creation_restriction(pattern, True, True) == "broad_creation_restriction"
    )


@pytest.mark.parametrize("pattern", [None, "", "?*", "[a-z]*", "*/*"])
def test_unrecognized_patterns_do_not_establish_shared_eligibility(pattern):
    assert (
        branch_creation_restriction(pattern, True, True)
        == "unknown_creation_restriction"
    )


@pytest.mark.parametrize("blocks,pushes", [(False, True), (True, False), (False, None)])
def test_inactive_creation_restrictions_do_not_exclude_repository(blocks, pushes):
    assert branch_creation_restriction("*", blocks, pushes) is None


@pytest.mark.parametrize("blocks,pushes", [(None, True), (True, None), (None, None)])
def test_missing_flags_are_not_treated_as_permission(blocks, pushes):
    assert (
        branch_creation_restriction("*", blocks, pushes)
        == "unknown_creation_restriction"
    )


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA github")
        ensure_optional_input_tables(con)
        ensure_app_installation_input_tables(con)
        con.execute(
            "INSERT INTO github.repositories (node_id, default_branch) VALUES ('R_1', 'main')"
        )
        con.execute(
            "INSERT INTO github.branches (id, name, repository_node_id) VALUES ('B_1', 'main', 'R_1')"
        )
        yield con


def add_rule(con, pattern, *, blocks=True, pushes=True, enforced=True, rule_id="RULE"):
    con.execute(
        """INSERT INTO github.branch_protection_rules
           (id, repository_node_id, pattern, blocks_creations, restricts_pushes,
            is_admin_enforced) VALUES (?, 'R_1', ?, ?, ?, ?)""",
        [rule_id, pattern, blocks, pushes, enforced],
    )


def eligible_repositories(con):
    branch_creation_eligibility(con)
    return con.execute(
        "SELECT repository_node_id FROM github.repositories_allowing_branch_creation"
    ).fetchall()


def test_shared_scope_eligibility_includes_unprotected_and_named_protection(connection):
    assert eligible_repositories(connection) == [("R_1",)]
    add_rule(connection, "main")
    add_rule(connection, "release/*", rule_id="RELEASE")
    assert eligible_repositories(connection) == [("R_1",)]


def test_substring_creation_restriction_leaves_repository_eligible(connection):
    add_rule(connection, "*protections_test*")
    assert eligible_repositories(connection) == [("R_1",)]


def test_substring_rule_does_not_cancel_a_broad_creation_restriction(connection):
    add_rule(connection, "*")
    add_rule(connection, "*protections_test*", rule_id="SUBSTRING")
    assert eligible_repositories(connection) == []


@pytest.mark.parametrize("pattern", ["*", "**/*", "[a-z]*"])
def test_broad_or_unrecognized_restrictions_exclude_shared_access(connection, pattern):
    add_rule(connection, pattern)
    assert eligible_repositories(connection) == []


def test_push_restrictions_without_creation_restrictions_still_allow_creation(
    connection,
):
    add_rule(connection, "*", blocks=False)
    assert eligible_repositories(connection) == [("R_1",)]


def test_missing_default_branch_does_not_establish_shared_eligibility(connection):
    connection.execute("DELETE FROM github.branches")
    assert eligible_repositories(connection) == []


def test_unresolved_protection_rule_does_not_look_unprotected(connection):
    connection.execute(
        "UPDATE github.branches SET branch_protection_rule = ?",
        [json.dumps({"id": "MISSING_RULE"})],
    )
    assert eligible_repositories(connection) == []


def test_restrictions_are_repository_specific(connection):
    connection.execute(
        "INSERT INTO github.repositories (node_id, default_branch) VALUES ('R_2', 'main')"
    )
    connection.execute(
        "INSERT INTO github.branches (id, name, repository_node_id) VALUES ('B_2', 'main', 'R_2')"
    )
    add_rule(connection, "*")
    assert eligible_repositories(connection) == [("R_2",)]


@pytest.mark.parametrize("enforced", [True, False, None])
def test_role_bypass_uses_shared_restrictions_without_changing_shared_scope(
    connection, enforced
):
    add_rule(connection, "*", enforced=enforced)
    connection.execute(
        """INSERT INTO github.repo_roles (id, repository_node_id, permissions)
           VALUES (1, 'R_1', '[]'),
                  (2, 'R_1', '["push_protected_branch"]'),
                  (3, 'R_1', NULL)"""
    )

    assert eligible_repositories(connection) == []
    role_can_create_branch(connection)
    rows = connection.execute("SELECT id FROM github.role_can_create_branch").fetchall()
    assert rows == ([(2,)] if enforced is False else [])


def test_specific_permissive_rule_does_not_override_broad_creation_restriction(
    connection,
):
    add_rule(connection, "*")
    add_rule(connection, "release", blocks=False, rule_id="NAMED_EXCEPTION")
    assert eligible_repositories(connection) == []


def test_rebuilding_eligibility_removes_stale_restrictions(connection):
    add_rule(connection, "*")
    assert eligible_repositories(connection) == []
    connection.execute("DELETE FROM github.branch_protection_rules")
    assert eligible_repositories(connection) == [("R_1",)]
