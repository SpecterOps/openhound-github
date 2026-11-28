import base64
from datetime import datetime

import duckdb
import msgpack
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.models.enterprise_role import EnterpriseRole
from openhound_github.models.enterprise_role_user import EnterpriseRoleUser
from openhound_github.models.org_role import OrgRole
from openhound_github.models.org_role_member import OrgRoleMember
from openhound_github.models.org_role_team import OrgRoleTeam
from openhound_github.models.repo_role_assignment import RepoRoleAssignment
from openhound_github.models.repository_role import RepoRole
from openhound_github.role_ids import role_node_id


def decode(value):
    namespace, kind, payload = value.split("_", 2)
    prefix = namespace + "_" + kind
    return prefix, msgpack.unpackb(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )


@pytest.mark.parametrize(
    "kind,prefix",
    [("repository", "GH_RR"), ("organization", "GH_OR"), ("enterprise", "GH_ER")],
)
@pytest.mark.parametrize("builtin,key", [(True, "owners"), (False, 38493)])
def test_role_encoding_is_versioned_scoped_and_namespaced(kind, prefix, builtin, key):
    value = role_node_id(kind, 2**40, key, builtin=builtin)
    assert decode(value) == (prefix, [1, 2**40, "builtin" if builtin else "api", key])
    assert value != role_node_id(kind, 2**40 + 1, key, builtin=builtin)
    assert value == role_node_id(kind, 2**40, key, builtin=builtin)
    assert "=" not in value


@pytest.mark.parametrize(
    "parent,key,builtin",
    [
        (None, 1, False),
        (0, 1, False),
        (True, 1, False),
        (1, 0, False),
        (1, None, False),
        (1, "1", False),
        (1, "", True),
        (1, 1, True),
    ],
)
def test_invalid_role_identity_fails_instead_of_falling_back_to_legacy(
    parent, key, builtin
):
    with pytest.raises(ValueError):
        role_node_id("repository", parent, key, builtin=builtin)


@pytest.fixture
def lookup():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA inventory")
    con.execute(
        "CREATE TABLE inventory.organizations (node_id VARCHAR, database_id BIGINT)"
    )
    con.execute("INSERT INTO inventory.organizations VALUES ('O_1', 101), ('O_2', 102)")
    con.execute(
        "CREATE TABLE inventory.repositories (node_id VARCHAR, database_id BIGINT)"
    )
    con.execute("INSERT INTO inventory.repositories VALUES ('R_1', 201), ('R_2', 202)")
    con.execute("CREATE TABLE inventory.enterprise (id VARCHAR, database_id BIGINT)")
    con.execute("INSERT INTO inventory.enterprise VALUES ('E_1', 301)")
    con.execute(
        "CREATE TABLE inventory.org_roles (org_node_id VARCHAR, id BIGINT, name VARCHAR, type VARCHAR, permissions JSON, org_login VARCHAR)"
    )
    con.execute(
        "INSERT INTO inventory.org_roles VALUES ('O_1', 1, 'owners', 'default', '[]', 'acme'), ('O_1', 33679, 'app_manager', 'custom', '[]', 'acme'), ('O_1', 5, 'custom', 'custom', '[\"view_secret_scanning_alerts\"]', 'acme')"
    )
    con.execute(
        "CREATE TABLE inventory.repo_roles (repository_node_id VARCHAR, id BIGINT, name VARCHAR, type VARCHAR, permissions JSON)"
    )
    con.execute(
        "INSERT INTO inventory.repo_roles VALUES ('R_1', 2, 'write', 'default', '[]'), ('R_1', 5, 'custom', 'custom', '[\"view_secret_scanning_alerts\"]')"
    )
    yield GithubLookup(con, schema="inventory")
    con.close()


def test_api_predefined_roles_use_api_namespace_and_nodes_preserve_raw_ids(lookup):
    role = OrgRole(
        id=33679,
        name="app_manager",
        type="custom",
        source="Predefined",
        org_node_id="O_1",
        org_login="acme",
        created_at=datetime(2026, 1, 1),
    )
    role._lookup = lookup
    node = role.as_node
    assert decode(node.id) == ("GH_OR", [1, 101, "api", 33679])
    assert (
        node.id
        == node.properties.node_id
        == lookup.org_role_node_id("O_1", "app_manager")
    )
    assert node.properties.github_role_id == 33679
    role.name = "renamed"
    assert role.node_id == node.id


def test_repository_nodes_and_assignments_share_ids_and_base_references(lookup):
    role = RepoRole(
        id=5,
        name="custom",
        base_role="write",
        type="custom",
        org_login="acme",
        repository_node_id="R_1",
        repository_name="repo",
        repository_full_name="acme/repo",
    )
    role._lookup = lookup
    node = role.as_node
    assert decode(node.id) == ("GH_RR", [1, 201, "api", 5])
    assert node.id == node.properties.node_id
    assert node.properties.github_role_id == 5
    base = next(role.edges)
    assert base.end.value == role_node_id("repository", 201, "write", builtin=True)
    assignment = RepoRoleAssignment(
        id=9,
        node_id="U_1",
        type="User",
        org_login="acme",
        assignee_type="user",
        repo_node_id="R_1",
        repo_name="repo",
        role_name="custom",
    )
    assignment._lookup = lookup
    assert next(assignment.edges).end.value == node.id
    role.name = "renamed"
    assert role.node_id == node.id


def test_organization_user_and_team_assignments_resolve_the_api_role_id(lookup):
    member = OrgRoleMember(
        id=9,
        node_id="U_1",
        login="alice",
        type="User",
        site_admin=False,
        org_role_id=33679,
        org_role_name="app_manager",
        org_node_id="O_1",
        org_login="acme",
    )
    team = OrgRoleTeam(
        id=8,
        node_id="T_1",
        url="",
        name="team",
        slug="team",
        permission="pull",
        members_url="",
        repositories_url="",
        org_role_id=33679,
        org_role_name="app_manager",
        org_node_id="O_1",
        org_login="acme",
    )
    for assignment in [member, team]:
        assignment._lookup = lookup
        assert next(assignment.edges).end.value == role_node_id(
            "organization", 101, 33679, builtin=False
        )


@pytest.mark.parametrize(
    "source,key,name,builtin",
    [
        ("Default", "owners", "owners", True),
        ("Predefined", "38493", "enterprise_app_manager", False),
    ],
)
def test_enterprise_nodes_and_assignments_share_both_namespaces(
    lookup, source, key, name, builtin
):
    role = EnterpriseRole(
        id=key,
        name=name,
        source=source,
        enterprise_node_id="E_1",
        enterprise_slug="acme",
    )
    role._lookup = lookup
    node = role.as_node
    assert decode(node.id) == (
        "GH_ER",
        [1, 301, "builtin" if builtin else "api", name if builtin else int(key)],
    )
    assert node.id == node.properties.node_id
    assert node.properties.github_role_id == key
    assignment = EnterpriseRoleUser(
        node_id="U_1",
        assignment="direct",
        role_id=key,
        enterprise_node_id="E_1",
        enterprise_slug="acme",
    )
    assignment._lookup = lookup
    assert next(assignment.edges).end.value == node.id


def test_role_lookup_queries_return_encoded_ids_for_downstream_capabilities(lookup):
    assert lookup.repo_role_node_ids_with_view_secret_scanning_alerts("R_1") == [
        (role_node_id("repository", 201, 5, builtin=False),)
    ]
    assert lookup.repo_role_node_ids_with_read_repo_contents("R_1") == [
        (role_node_id("repository", 201, "write", builtin=True),)
    ]
    assert set(lookup.org_role_node_ids_with_view_secret_scanning_alerts("acme")) == {
        (role_node_id("organization", 101, 5, builtin=False),),
        (role_node_id("organization", 101, "owners", builtin=True),),
    }


def test_missing_parent_ids_fail_and_missing_api_role_definitions_are_not_fabricated(
    lookup,
):
    assert lookup.org_role_node_id("O_1", "missing") is None
    assert lookup.repo_role_node_id("R_1", "missing") is None
    with pytest.raises(ValueError, match="Missing organization database ID"):
        lookup.org_role_node_id("missing", "owners")
