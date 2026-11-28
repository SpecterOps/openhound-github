from datetime import datetime, timezone
import json

import duckdb
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.personal_access_token import PersonalAccessToken
from openhound_github.models.personal_access_token_request import (
    PersonalAccessTokenRequest,
)
from openhound_github.models.scope import scope_node_id
from openhound_github.transforms import (
    branch_creation_eligibility,
    ensure_app_installation_input_tables,
    ensure_optional_input_tables,
    role_can_create_branch,
)


SCOPE = scope_node_id("O_1", "repository_branch_creation", "unrestricted")


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        ensure_optional_input_tables(con, "inventory")
        ensure_app_installation_input_tables(con, "inventory")
        con.execute(
            "CREATE TABLE inventory.organizations (node_id VARCHAR, login VARCHAR, database_id BIGINT)"
        )
        con.execute("INSERT INTO inventory.organizations VALUES ('O_1', 'Acme', 123)")
        con.execute("""INSERT INTO inventory.repositories (node_id, org_login, default_branch) VALUES
            ('R_A', 'Acme', 'main'), ('R_B', 'Acme', 'main'), ('R_BLOCKED', 'Acme', 'main'),
            ('R_OTHER', 'Other', 'main'), ('R_UNCOLLECTED', 'Acme', 'main')""")
        con.execute("""INSERT INTO inventory.branches (id, name, repository_node_id)
            SELECT 'B_' || node_id, 'main', node_id FROM inventory.repositories
            WHERE node_id <> 'R_UNCOLLECTED'""")
        con.execute("""INSERT INTO inventory.scopes VALUES
            ('Acme', 'O_1', 'repository_branch_creation', 'unrestricted')""")
        con.execute("""INSERT INTO inventory.repo_roles (id, name, repository_node_id, permissions)
            SELECT row_number() OVER (), role, r.node_id, '[]'
            FROM inventory.repositories r CROSS JOIN (VALUES ('read'), ('write'), ('maintain'), ('admin'), ('custom')) roles(role)""")
        rule(con)
        yield con


def rule(
    con,
    *,
    rule_id="RULE",
    actor_id=None,
    actor_type="User",
    enforced=True,
    pattern="**",
):
    nodes = (
        []
        if actor_id is None
        else [{"actor": {"__typename": actor_type, "id": actor_id}}]
    )
    con.execute(
        """INSERT INTO inventory.branch_protection_rules
        (id, repository_node_id, pattern, blocks_creations, restricts_pushes, is_admin_enforced, push_allowances)
        VALUES (?, 'R_BLOCKED', ?, true, true, ?, ?)""",
        [rule_id, pattern, enforced, json.dumps({"nodes": nodes})],
    )


def grant(
    con,
    repo="R_A",
    role="write",
    *,
    actor="U_1",
    actor_type="user",
    base=None,
    permissions=None,
):
    con.execute(
        """INSERT INTO inventory.repo_role_assignments
        (node_id, assignee_type, repo_node_id, role_name, base_role, role_permissions)
        VALUES (?, ?, ?, ?, ?, ?)""",
        [actor, actor_type, repo, role, base, json.dumps(permissions or [])],
    )
    con.execute(
        """UPDATE inventory.repo_roles SET base_role = ?, permissions = ?
        WHERE repository_node_id = ? AND name = ?""",
        [base, json.dumps(permissions or []), repo, role],
    )


def membership(con, *, nested=False):
    con.execute(
        "INSERT INTO inventory.team_members (team_id, id) VALUES ('T_CHILD', 'U_1')"
    )
    if nested:
        con.execute(
            "INSERT INTO inventory.teams (id, parent_team) VALUES (?, ?)",
            ["T_CHILD", json.dumps({"id": "T_PARENT"})],
        )
    return "T_PARENT" if nested else "T_CHILD"


def token(con, **overrides):
    branch_creation_eligibility(con, "inventory")
    role_can_create_branch(con, "inventory")
    asset = PersonalAccessToken.model_validate(
        {
            "id": 10,
            "token_id": 900,
            "token_name": "automation",
            "token_expired": False,
            "owner": {"login": "alice", "id": 1, "node_id": "U_1", "type": "User"},
            "permissions": {"repository": {"contents": "write"}},
            "repository_selection": "all",
            "org_login": "aCME",
            **overrides,
        }
    )
    asset._lookup = GithubLookup(con, "inventory")
    return asset


def capabilities(con, **overrides):
    return [
        edge
        for edge in token(con, **overrides).edges
        if edge.kind == ek.CAN_CREATE_BRANCH
    ]


def targets(con, **overrides):
    return {edge.end.value for edge in capabilities(con, **overrides)}


@pytest.mark.parametrize("owner_role", [None, "read"])
def test_pat_contents_write_cannot_exceed_owners_repository_authority(
    connection, owner_role
):
    if owner_role:
        grant(connection, role=owner_role)
    assert targets(connection) == set()


def test_partial_owner_access_never_receives_the_all_repository_scope(connection):
    grant(connection)
    edges = capabilities(connection)
    assert {e.end.value for e in edges} == {"R_A"}
    assert all(e.properties.composed and e.properties.traversable for e in edges)
    assert all("owner_access" in e.properties.query_composition for e in edges)
    assert all("node_id:'U_1'" in e.properties.query_composition for e in edges)


def test_existing_owner_creation_capability_is_required_even_with_write_role(
    connection,
):
    grant(connection)
    asset = token(connection)
    connection.execute("DELETE FROM inventory.role_can_create_branch")
    assert list(asset._can_create_branch_edges) == []


def test_pat_cannot_borrow_another_users_authority(connection):
    grant(connection, role="read")
    grant(connection, role="admin", actor="U_OTHER")
    assert targets(connection) == set()


def test_scope_requires_owner_authority_over_every_member(connection):
    grant(connection)
    grant(connection, "R_B")
    edges = capabilities(connection)
    assert {e.end.value for e in edges} == {SCOPE}
    assert "RETURN p, p1, owner_access" in edges[0].properties.query_composition


@pytest.mark.parametrize("selection", ["selected", "subset"])
def test_selected_grants_are_intersected_with_owner_authority(connection, selection):
    grant(connection)
    connection.execute(
        "INSERT INTO inventory.pat_repo_access VALUES (10, 'R_A', 'Acme'), (10, 'R_B', 'Acme'), (10, 'R_OTHER', 'Other')"
    )
    assert targets(connection, repository_selection=selection) == {"R_A"}


def test_selected_access_cannot_be_borrowed_from_another_token(connection):
    grant(connection)
    connection.execute(
        "INSERT INTO inventory.pat_repo_access VALUES (99, 'R_A', 'Acme')"
    )
    assert targets(connection, repository_selection="subset") == set()


@pytest.mark.parametrize(
    "settings",
    [
        {"token_expired": True},
        {"token_expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
        {"expires_at": datetime(2000, 1, 1)},
        {"permissions": {"repository": {"contents": "read"}}},
        {"permissions": {}},
        {"repository_selection": "none"},
        {"repository_selection": None},
    ],
)
def test_ineligible_pat_never_emits_creation_capabilities(connection, settings):
    grant(connection)
    grant(connection, "R_B")
    assert targets(connection, **settings) == set()


def test_owner_authority_flows_through_nested_teams(connection):
    parent = membership(connection, nested=True)
    grant(connection, actor=parent, actor_type="team")
    assert targets(connection) == {"R_A"}


@pytest.mark.parametrize(
    "via", ["owner", "members_base", "custom_org_role", "team_org_role"]
)
def test_owner_authority_flows_through_organization_roles(connection, via):
    if via in {"owner", "members_base"}:
        if via == "owner":
            connection.execute(
                "INSERT INTO inventory.org_roles (name, base_role, org_login) VALUES ('owners', 'admin', 'Acme')"
            )
        connection.execute(
            "INSERT INTO inventory.users (id, role, org_login) VALUES ('U_1', ?, 'Acme')",
            ["ADMIN" if via == "owner" else "MEMBER"],
        )
        if via == "members_base":
            connection.execute(
                "INSERT INTO inventory.org_roles (name, base_role, org_login) VALUES ('members', 'write', 'Acme')"
            )
    else:
        connection.execute(
            "INSERT INTO inventory.org_roles (name, base_role, org_login) VALUES ('Developer', 'write', 'Acme')"
        )
        if via == "custom_org_role":
            connection.execute(
                "INSERT INTO inventory.org_role_members VALUES ('U_1', 'Developer', 'Acme')"
            )
        else:
            team = membership(connection)
            connection.execute(
                "INSERT INTO inventory.org_role_teams VALUES (?, 'Developer', 'Acme')",
                [team],
            )
    assert targets(connection) == {SCOPE}


@pytest.mark.parametrize("enforced", [False, True, None])
@pytest.mark.parametrize(
    "role,base,permissions",
    [
        ("admin", None, []),
        ("custom", "admin", []),
        ("write", None, ["push_protected_branch"]),
    ],
)
def test_admin_exemption_requires_explicitly_disabled_enforcement(
    connection, enforced, role, base, permissions
):
    connection.execute("DELETE FROM inventory.branch_protection_rules")
    rule(connection, enforced=enforced)
    grant(connection, "R_BLOCKED", role, base=base, permissions=permissions)
    assert targets(connection) == ({"R_BLOCKED"} if enforced is False else set())


@pytest.mark.parametrize(
    "actor_type,actor_id,expected",
    [
        ("User", "U_1", set()),
        ("User", "U_OTHER", set()),
        ("Team", "T_PARENT", set()),
        ("App", "U_1", set()),
    ],
)
def test_allowance_cannot_exceed_modeled_owner_creation_capability(
    connection, actor_type, actor_id, expected
):
    connection.execute("DELETE FROM inventory.branch_protection_rules")
    rule(connection, actor_type=actor_type, actor_id=actor_id)
    membership(connection, nested=True)
    grant(connection, "R_BLOCKED")
    edges = capabilities(connection)
    assert {e.end.value for e in edges} == expected
    if edges:
        assert "GH_RestrictionsCanPush" in edges[0].properties.query_composition
        assert "owner_access" in edges[0].properties.query_composition


@pytest.mark.parametrize("pattern", ["**", "?*"])
def test_all_protections_must_have_positive_owner_evidence(connection, pattern):
    connection.execute("DELETE FROM inventory.branch_protection_rules")
    rule(connection, actor_id="U_1")
    rule(connection, rule_id="SECOND", pattern=pattern)
    grant(connection, "R_BLOCKED")
    assert targets(connection) == set()


@pytest.mark.parametrize("flag", ["archived", "disabled"])
def test_read_only_repositories_never_receive_capabilities(connection, flag):
    connection.execute(
        f"UPDATE inventory.repositories SET {flag} = true WHERE node_id = 'R_A'"
    )
    grant(connection)
    assert targets(connection) == set()


def test_missing_branch_evidence_never_receives_capability(connection):
    grant(connection, "R_UNCOLLECTED")
    assert targets(connection) == set()


def test_scope_absent_in_older_collection_uses_direct_edges(connection):
    connection.execute("DELETE FROM inventory.scopes")
    grant(connection)
    grant(connection, "R_B")
    assert targets(connection) == {"R_A", "R_B"}


def test_pending_request_does_not_inherit_active_pat_capabilities(connection):
    grant(connection)
    pat = token(connection)
    data = pat.model_dump()
    data["owner"]["site_admin"] = False
    request = PersonalAccessTokenRequest.model_validate(data)
    request._lookup = pat._lookup
    assert not any(e.kind == ek.CAN_CREATE_BRANCH for e in request.edges)
