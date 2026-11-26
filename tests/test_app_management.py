from datetime import datetime
import json

import duckdb
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import AppInstallation
from openhound_github.models.enterprise_role import EnterpriseRole
from openhound_github.models.org_role import OrgRole
from openhound_github.transforms import (
    ensure_app_installation_input_tables,
    ensure_optional_input_tables,
)


@pytest.fixture
def lookup():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        ensure_optional_input_tables(con, "inventory")
        ensure_app_installation_input_tables(con, "inventory")
        con.execute(
            "CREATE TABLE inventory.organizations (node_id VARCHAR, login VARCHAR)"
        )
        con.execute(
            "INSERT INTO inventory.organizations VALUES ('ORG_A','a'), ('ORG_B','b')"
        )
        con.execute(
            "INSERT INTO inventory.enterprise (id, slug) VALUES ('ENT_A','enterprise-a')"
        )
        con.execute("ALTER TABLE inventory.applications ADD COLUMN slug VARCHAR")
        con.execute(
            "ALTER TABLE inventory.applications ADD COLUMN environment_slug VARCHAR"
        )
        for node_id, owner_id, owner_type, slug, environment in [
            ("APP_A", "ORG_A", "Organization", "owned-app", "a"),
            ("APP_A", "ORG_A", "Organization", "owned-app", "b"),
            ("APP_B", "ORG_B", "Organization", "other-app", "a"),
            ("APP_ENTERPRISE", "ENT_A", "Enterprise", "enterprise-app", "a"),
            ("APP_PERSONAL", "USER_A", "User", "personal-app", "a"),
            ("APP_THIRD_PARTY", "EXTERNAL_ORG", "Organization", "third-party-app", "a"),
            ("APP_TYPE_MISMATCH", "ORG_A", "User", "mismatched-app", "a"),
        ]:
            con.execute(
                "INSERT INTO inventory.applications VALUES (?, ?, ?, ?)",
                [
                    node_id,
                    json.dumps({"node_id": owner_id, "type": owner_type}),
                    slug,
                    environment,
                ],
            )
        yield GithubLookup(con, schema="inventory")


def org_role(
    lookup, name="app_manager", role_type="custom", source="Predefined", account="ORG_A"
):
    role = OrgRole(
        id=33679,
        name=name,
        type=role_type,
        source=source,
        permissions=[],
        org_node_id=account,
        org_login="a",
        created_at=datetime(2026, 1, 1),
    )
    role._lookup = lookup
    return role


def enterprise_role(
    lookup, name="enterprise_app_manager", source="Predefined", account="ENT_A"
):
    role = EnterpriseRole(
        id="38493",
        name=name,
        source=source,
        permissions=[],
        enterprise_node_id=account,
        enterprise_slug="enterprise-a",
    )
    role._lookup = lookup
    return role


def management_edges(role):
    return [edge for edge in role.edges if edge.kind == ek.CAN_MANAGE_APP]


@pytest.mark.parametrize(
    "name,source,role_type",
    [
        ("app_manager", "Predefined", "custom"),
        ("owners", None, "default"),
    ],
)
def test_organization_roles_control_only_registration_owned_apps(
    lookup, name, source, role_type
):
    role = org_role(lookup, name, role_type, source)
    edges = management_edges(role)
    assert (
        len(edges) == 1
    )  # Repeated installation-context observations are deduplicated.
    edge = edges[0]
    assert edge.start.value == role.node_id
    assert edge.end.value == "APP_A"
    assert edge.properties.traversable is True
    assert edge.properties.composed is True
    assert edge.properties.reason == (
        "owner_role" if name == "owners" else "app_manager_role"
    )
    query = edge.properties.query_composition
    assert "GH_OrgRole" in query and "GH_Organization" in query
    assert "GH_Contains" in query and "GH_Owns" in query
    assert role.node_id in query and "ORG_A" in query and "APP_A" in query
    assert "role.source = 'Predefined'" in query
    assert role.as_node.properties.source == source


@pytest.mark.parametrize(
    "name,source",
    [
        ("enterprise_app_manager", "Predefined"),
        ("owners", "Default"),
    ],
)
def test_enterprise_roles_do_not_inherit_organization_owned_apps(lookup, name, source):
    role = enterprise_role(lookup, name, source)
    (edge,) = management_edges(role)
    assert edge.start.value == role.node_id
    assert edge.end.value == "APP_ENTERPRISE"
    assert edge.properties.traversable and edge.properties.composed
    assert "GH_EnterpriseRole" in edge.properties.query_composition
    assert "account:GH_Enterprise" in edge.properties.query_composition


@pytest.mark.parametrize(
    "name,role_type,source",
    [
        ("app_manager", "custom", None),
        ("owners", "custom", "Organization"),
        ("App Manager", "custom", "Predefined"),
        ("members", "default", None),
        ("security_manager", "custom", "Predefined"),
        ("app_manager", "default", "Organization"),
    ],
)
def test_custom_or_unrelated_organization_roles_do_not_get_control(
    lookup, name, role_type, source
):
    assert management_edges(org_role(lookup, name, role_type, source)) == []


@pytest.mark.parametrize(
    "name,source",
    [
        ("enterprise_app_manager", "Enterprise"),
        ("owners", None),
        ("app_manager", "Predefined"),
        ("members", "Default"),
        ("enterprise_app_manager_copy", "Predefined"),
    ],
)
def test_custom_or_unrelated_enterprise_roles_do_not_get_control(lookup, name, source):
    assert management_edges(enterprise_role(lookup, name, source)) == []


def test_app_management_is_scoped_to_exact_account_id(lookup):
    assert {
        edge.end.value for edge in management_edges(org_role(lookup, account="ORG_B"))
    } == {"APP_B"}
    assert management_edges(org_role(lookup, account="MISSING_ORG")) == []
    assert management_edges(enterprise_role(lookup, account="MISSING_ENTERPRISE")) == []


def test_missing_owner_and_empty_app_inventory_do_not_grant_control(lookup):
    lookup.client.execute("DELETE FROM inventory.applications")
    lookup.client.execute(
        "INSERT INTO inventory.applications (node_id, owner) VALUES ('UNKNOWN', NULL)"
    )
    assert management_edges(org_role(lookup)) == []
    assert management_edges(enterprise_role(lookup)) == []


def test_account_must_exist_even_when_app_owner_metadata_matches(lookup):
    lookup.client.execute("DELETE FROM inventory.organizations WHERE node_id='ORG_A'")
    assert management_edges(org_role(lookup)) == []


def test_control_flows_to_existing_installations_in_other_accounts(lookup):
    (control,) = management_edges(org_role(lookup))
    installation = AppInstallation(
        id=99,
        app_id=1,
        app_slug="owned-app",
        target_type="Organization",
        repository_selection="selected",
        permissions={"contents": "read"},
        org_login="b",
        created_at=datetime(2026, 1, 1),
    )
    installation._lookup = lookup
    (installed_as,) = [
        edge for edge in installation.edges if edge.kind == ek.INSTALLED_AS
    ]
    assert control.end.value == installed_as.start.value == "APP_A"
    assert installed_as.end.value == "GH_AppInstallation_99"
    assert installed_as.properties.traversable is True
    assert all(edge.end.value != "APP_B" for edge in management_edges(org_role(lookup)))


def test_ownership_comparison_preserves_node_id_case(lookup):
    assert lookup.app_node_ids_owned_by("org_a", "Organization") == []
    assert lookup.app_node_ids_owned_by("ORG_A", "Enterprise") == []
