from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import AppInstallation
from openhound_github.models.branch_creation import branch_creation_edges
from openhound_github.models.scope import (
    REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
    UNRESTRICTED_BRANCH_CREATION_SCOPE,
    Scope,
    scope_node_id,
)
from openhound_github.resources.organization import scopes
from openhound_github.transforms import (
    branch_creation_eligibility,
    ensure_app_installation_input_tables,
    ensure_optional_input_tables,
)


SCOPE_ID = scope_node_id("O_1", "repository_branch_creation", "unrestricted")


def add_rule(con, repo_id, *, actor="release-app", pattern="*", rule_id="RULE"):
    nodes = (
        []
        if actor is None
        else [{"actor": {"__typename": "App", "id": "APP_7", "slug": actor}}]
    )
    con.execute(
        """INSERT INTO inventory.branch_protection_rules
        (id, repository_node_id, pattern, blocks_creations, restricts_pushes,
         is_admin_enforced, push_allowances) VALUES (?, ?, ?, true, true, true, ?)""",
        [rule_id, repo_id, pattern, json.dumps({"nodes": nodes})],
    )


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        ensure_optional_input_tables(con, "inventory")
        ensure_app_installation_input_tables(con, "inventory")
        con.execute(
            "CREATE TABLE inventory.organizations (node_id VARCHAR, login VARCHAR)"
        )
        con.execute("INSERT INTO inventory.organizations VALUES ('O_1', 'acme')")
        con.execute(
            """INSERT INTO inventory.repositories
            (node_id, database_id, org_login, default_branch) VALUES
            ('R_OPEN', 1, 'acme', 'main'), ('R_NAMED', 2, 'acme', 'main'),
            ('R_EXCEPTION', 3, 'acme', 'main'), ('R_DENIED', 4, 'acme', 'main'),
            ('R_OTHER_ORG', 5, 'other', 'main'), ('R_UNCOLLECTED', 6, 'acme', 'main')"""
        )
        con.execute(
            """INSERT INTO inventory.branches (id, name, repository_node_id)
            SELECT 'B_' || node_id, 'main', node_id FROM inventory.repositories
            WHERE node_id <> 'R_UNCOLLECTED'"""
        )
        add_rule(con, "R_NAMED", pattern="release/*", rule_id="NAMED")
        add_rule(con, "R_EXCEPTION", rule_id="EXCEPTION")
        add_rule(con, "R_DENIED", actor=None, rule_id="DENIED")
        rows = list(scopes.__wrapped__(SimpleNamespace(login="acme", node_id="O_1")))
        con.executemany(
            "INSERT INTO inventory.scopes VALUES (?, ?, ?, ?)",
            [
                (row["org_login"], row["org_node_id"], row["scope_type"], row["scope"])
                for row in rows
            ],
        )
        yield con


def installation(
    con,
    *,
    selection="all",
    permissions=None,
    suspended=None,
    target="Organization",
    org="acme",
    installation_id=42,
):
    permissions = {"contents": "write"} if permissions is None else permissions
    con.execute(
        """INSERT INTO inventory.app_installations
        (id, app_slug, target_type, repository_selection, environment_slug,
         suspended_at, permissions) VALUES (?, 'release-app', ?, ?, ?, ?, ?)""",
        [installation_id, target, selection, org, suspended, json.dumps(permissions)],
    )
    branch_creation_eligibility(con, "inventory")
    model = AppInstallation(
        id=installation_id,
        app_id=7,
        app_slug="release-app",
        target_type=target,
        repository_selection=selection,
        permissions=permissions,
        environment_slug=org,
        suspended_at=suspended,
        created_at=datetime(2026, 1, 1),
    )
    model._lookup = GithubLookup(con, schema="inventory")
    return model


def capability_edges(model):
    return [edge for edge in model.edges if edge.kind == ek.CAN_CREATE_BRANCH]


def test_all_access_uses_shared_scope_plus_direct_app_exception(connection):
    model = installation(connection)
    edges = capability_edges(model)
    assert {edge.end.value for edge in edges} == {SCOPE_ID, "R_EXCEPTION"}
    assert all(
        edge.properties.traversable and edge.properties.composed for edge in edges
    )
    assert all("contents:write" in edge.properties.query_composition for edge in edges)
    exception = next(edge for edge in edges if edge.end.value == "R_EXCEPTION")
    assert exception.properties.reason == "app_push_allowance"
    assert "GH_RestrictionsCanPush" in exception.properties.query_composition

    scope = Scope(
        org_login="acme",
        org_node_id="O_1",
        scope_type=REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
        scope=UNRESTRICTED_BRANCH_CREATION_SCOPE,
    )
    scope._lookup = model._lookup
    assert scope.as_node.id == SCOPE_ID
    assert scope.as_node.properties.member_count == 2
    members = [edge for edge in scope.edges if edge.kind == ek.SCOPED_TO]
    assert {edge.end.value for edge in members} == {"R_OPEN", "R_NAMED"}
    assert all(
        edge.start.value == SCOPE_ID and edge.properties.traversable for edge in members
    )


@pytest.mark.parametrize("selection", ["all", "selected"])
def test_mixed_case_organization_emits_creation_capabilities(connection, selection):
    connection.execute("UPDATE inventory.organizations SET login = 'AcMe'")
    connection.executemany(
        "INSERT INTO inventory.app_installation_repo_access VALUES (?, ?, ?)",
        [("GH_AppInstallation_42", 1, "acme"), ("GH_AppInstallation_42", 3, "acme")],
    )

    edges = capability_edges(installation(connection, org="ACME", selection=selection))

    assert {edge.end.value for edge in edges} == {
        SCOPE_ID if selection == "all" else "R_OPEN",
        "R_EXCEPTION",
    }
    assert all(edge.start.value == "GH_AppInstallation_42" for edge in edges)
    assert all(edge.properties.traversable for edge in edges)


def test_selected_access_only_reaches_granted_repositories(connection):
    connection.executemany(
        "INSERT INTO inventory.app_installation_repo_access VALUES (?, ?, ?)",
        [
            ("GH_AppInstallation_42", 1, "acme"),
            ("GH_AppInstallation_42", 3, "acme"),
            ("GH_AppInstallation_42", 5, "other"),
            ("GH_AppInstallation_43", 2, "acme"),
        ],
    )
    model = installation(connection, selection="selected")
    assert {edge.end.value for edge in capability_edges(model)} == {
        "R_OPEN",
        "R_EXCEPTION",
    }


@pytest.mark.parametrize(
    "settings",
    [
        {"permissions": {"contents": "read"}},
        {"permissions": {}},
        {"permissions": {"administration": "write"}},
        {"suspended": "2026-11-25T00:00:00Z"},
        {"target": "Enterprise"},
        {"selection": "selected"},
        {"selection": None},
        {"org": "unknown"},
    ],
)
def test_ineligible_installations_have_no_creation_paths(connection, settings):
    assert capability_edges(installation(connection, **settings)) == []


def test_empty_shared_scope_has_no_incoming_capability_edge(connection):
    add_rule(connection, "R_OPEN", actor=None, rule_id="BLOCK_OPEN")
    add_rule(connection, "R_NAMED", actor=None, rule_id="BLOCK_NAMED")
    model = installation(connection)
    assert {edge.end.value for edge in capability_edges(model)} == {"R_EXCEPTION"}


def test_older_collection_without_scope_uses_direct_edges(connection):
    connection.execute(
        "DELETE FROM inventory.scopes WHERE scope_type = 'repository_branch_creation'"
    )
    model = installation(connection)
    assert {edge.end.value for edge in capability_edges(model)} == {
        "R_OPEN",
        "R_NAMED",
        "R_EXCEPTION",
    }


def test_substring_restriction_does_not_require_app_exception(connection):
    connection.execute(
        "UPDATE inventory.branch_protection_rules "
        "SET pattern = '*protections_test*', push_allowances = NULL WHERE id = 'NAMED'"
    )
    model = installation(connection)
    assert ("R_NAMED",) in model._lookup.branch_creation_repositories_for_org("acme")
    assert {edge.end.value for edge in capability_edges(model)} == {
        SCOPE_ID,
        "R_EXCEPTION",
    }


@pytest.mark.parametrize(
    "change",
    [
        "wrong_app",
        "wrong_type",
        "second_blocker",
        "unknown_pattern",
        "missing_reference",
    ],
)
def test_app_exception_requires_complete_matching_evidence(connection, change):
    if change in {"wrong_app", "wrong_type"}:
        actor = {
            "__typename": "Team" if change == "wrong_type" else "App",
            "id": "APP_7",
            "slug": "other-app" if change == "wrong_app" else "release-app",
        }
        connection.execute(
            "UPDATE inventory.branch_protection_rules SET push_allowances = ? WHERE id = 'EXCEPTION'",
            [json.dumps({"nodes": [{"actor": actor}]})],
        )
    elif change == "second_blocker":
        add_rule(connection, "R_EXCEPTION", actor=None, rule_id="SECOND_BLOCKER")
    elif change == "unknown_pattern":
        connection.execute(
            "UPDATE inventory.branch_protection_rules SET pattern = '?*' WHERE id = 'EXCEPTION'"
        )
    else:
        connection.execute(
            "UPDATE inventory.branches SET branch_protection_rule = '{\"id\":\"MISSING\"}' WHERE repository_node_id = 'R_EXCEPTION'"
        )
    assert "R_EXCEPTION" not in {
        edge.end.value for edge in capability_edges(installation(connection))
    }


@pytest.mark.parametrize("flag", ["archived", "disabled"])
def test_read_only_repositories_have_no_capability_paths(connection, flag):
    connection.execute(
        f"UPDATE inventory.repositories SET {flag} = true WHERE org_login = 'acme'"
    )
    assert capability_edges(installation(connection)) == []


def test_multiple_installations_reuse_one_scope(connection):
    first = installation(connection)
    second = installation(connection, installation_id=43)
    edges = [
        edge
        for model in (first, second)
        for edge in capability_edges(model)
        if edge.end.value == SCOPE_ID
    ]
    assert len(edges) == 2
    assert {edge.start.value for edge in edges} == {
        "GH_AppInstallation_42",
        "GH_AppInstallation_43",
    }


def test_native_actor_typename_is_accepted_in_app_exception(connection):
    connection.execute(
        "UPDATE inventory.branch_protection_rules SET push_allowances = ? WHERE id = 'EXCEPTION'",
        [
            json.dumps(
                {
                    "nodes": [
                        {
                            "actor": {
                                "typename": "App",
                                "id": "APP_7",
                                "slug": "release-app",
                            }
                        }
                    ]
                }
            )
        ],
    )
    assert "R_EXCEPTION" in {
        edge.end.value for edge in capability_edges(installation(connection))
    }


def test_explore_queries_resolve_both_direct_and_scoped_capabilities():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "extension/schema.json").read_text())
    nodes = {node["name"]: node for node in schema["node_kinds"]}
    for kind, panel in [
        ("GH_AppInstallation", "branch_creation_repositories"),
        ("GH_Repository", "branch_creators"),
    ]:
        query = nodes[kind]["info"][panel]["markdown"]["content"]
        assert "GH_CanCreateBranch" in query
        assert "GH_ScopedTo*0..1" in query
    assert (
        "GH_CanCreateBranch"
        in nodes["GH_Scope"]["info"]["inbound_traversable_relationships"]["markdown"][
            "content"
        ]
    )
    search = json.loads(
        (
            root / "extension/saved_searches/app-installations-can-create-branches.json"
        ).read_text()
    )
    assert "GH_CanCreateBranch" in search["query"]
    assert "GH_ScopedTo*0..1" in search["query"]


@pytest.mark.parametrize("bypass", [False, None, True])
@pytest.mark.parametrize("exclude_shared", [False, True])
def test_shared_evaluator_accepts_credential_policy_and_requires_positive_bypass(
    connection, bypass, exclude_shared
):
    branch_creation_eligibility(connection, "inventory")
    lookup = GithubLookup(connection, schema="inventory")
    rows = lookup._branch_creation_repositories_for_access(
        "ACME",
        access_query="""SELECT node_id AS repository_node_id,
                       CAST(? AS BOOLEAN) AS can_bypass FROM inventory.repositories""",
        access_parameters=[bypass],
        restriction_bypass_query="access.can_bypass",
        bypass_reason="test_actor_allowance",
        exclude_shared=exclude_shared,
    )
    expected = set()
    if not exclude_shared:
        expected |= {
            ("R_OPEN", "shared_creation_eligibility"),
            ("R_NAMED", "shared_creation_eligibility"),
        }
    if bypass is True:
        expected |= {
            ("R_EXCEPTION", "test_actor_allowance"),
            ("R_DENIED", "test_actor_allowance"),
        }
    assert set(rows) == expected


@pytest.mark.parametrize("second_pattern", ["*", "?*"])
def test_shared_evaluator_requires_every_restriction_to_have_known_bypass(
    connection, second_pattern
):
    add_rule(connection, "R_EXCEPTION", pattern=second_pattern, rule_id="SECOND")
    branch_creation_eligibility(connection, "inventory")
    lookup = GithubLookup(connection, schema="inventory")
    rows = lookup._branch_creation_repositories_for_access(
        "acme",
        access_query="SELECT 'R_EXCEPTION' AS repository_node_id",
        access_parameters=[],
        restriction_bypass_query="restriction.rule_id = 'EXCEPTION'",
        bypass_reason="test_actor_allowance",
    )
    assert rows == []


@pytest.mark.parametrize("allow_shared_scope", [False, True])
def test_shared_edge_builder_requires_explicit_authority_for_scope_members(
    connection, allow_shared_scope
):
    branch_creation_eligibility(connection, "inventory")
    lookup = GithubLookup(connection, schema="inventory")
    exclusions = []

    def resolve(exclude_shared):
        exclusions.append(exclude_shared)
        return [] if exclude_shared else [("R_OPEN", "shared_creation_eligibility")]

    edges = list(
        branch_creation_edges(
            lookup,
            credential_node_id="TEST_CREDENTIAL",
            org_login="acme",
            org_node_id="O_1",
            allow_shared_scope=allow_shared_scope,
            resolve_repositories=resolve,
            access_query="MATCH p=(credential)-[:GH_CanAccess]->(repository) WHERE true ",
            repository_evidence_queries={},
        )
    )
    assert {edge.end.value for edge in edges} == (
        {SCOPE_ID} if allow_shared_scope else {"R_OPEN"}
    )
    assert exclusions == [allow_shared_scope]
    assert all(edge.start.value == "TEST_CREDENTIAL" for edge in edges)
    assert all(
        edge.properties.traversable and edge.properties.composed for edge in edges
    )
