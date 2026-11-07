from unittest.mock import MagicMock

import duckdb
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.models.app_installation import App, Owner


def _app(owner: Owner | None) -> App:
    return App(
        id=123,
        slug="example-app",
        client_id="Iv1.example",
        node_id="APP_NODE_123",
        owner=owner,
        name="Example App",
        permissions={},
        events=[],
        org_login="installed-org",
        org_node_id="ORG_NODE_789",
    )


def _owner(owner_type: str, node_id: str = "OWNER_NODE_456") -> Owner:
    return Owner(
        login="example-owner",
        id=456,
        node_id=node_id,
        type=owner_type,
    )


def test_app_node_includes_registration_owner_properties() -> None:
    app = _app(_owner("Organization"))
    lookup = MagicMock()
    lookup.is_tenant_organization_node_id.return_value = True
    app._lookup = lookup

    properties = app.as_node.properties

    assert properties.owner_login == "example-owner"
    assert properties.owner_node_id == "OWNER_NODE_456"
    assert properties.owner_type == "Organization"
    assert properties.query_owner == (
        "MATCH p=(owner)-[:GH_Owns]->"
        "(:GH_App {node_id:'APP_NODE_123'}) RETURN p"
    )


@pytest.mark.parametrize(
    ("owner_type", "owner_node_id", "tenant_org", "enterprise_id", "expected"),
    [
        ("Organization", "ORG_NODE_1", True, "ENT_NODE_1", "tenant_owned"),
        ("Organization", "EXTERNAL_ORG", False, "ENT_NODE_1", "third_party"),
        ("Organization", "ORG_NODE_1", True, None, "tenant_owned"),
        ("Organization", "UNRESOLVED_ORG", False, None, "third_party"),
        ("User", "USER_NODE_1", False, "ENT_NODE_1", "third_party"),
        ("User", "USER_NODE_1", False, None, "third_party"),
        ("Enterprise", "ENT_NODE_1", False, "ENT_NODE_1", "tenant_owned"),
        ("Enterprise", "EXTERNAL_ENT", False, "ENT_NODE_1", "third_party"),
        ("Enterprise", "ENT_NODE_1", False, None, "third_party"),
        ("Bot", "BOT_NODE_1", False, "ENT_NODE_1", "unknown"),
    ],
)
def test_app_classifies_registration_origin(
    owner_type: str,
    owner_node_id: str,
    tenant_org: bool,
    enterprise_id: str | None,
    expected: str,
) -> None:
    app = _app(_owner(owner_type, owner_node_id))
    lookup = MagicMock()
    lookup.is_tenant_organization_node_id.return_value = tenant_org
    lookup.is_collected_user_node_id.return_value = False
    lookup.enterprise_id.return_value = enterprise_id
    app._lookup = lookup

    assert app.as_node.properties.registration_origin == expected


@pytest.mark.parametrize(
    ("owner_node_id", "expected"),
    [
        ("USER_ORG", "member_owned"),
        ("USER_ENTERPRISE", "member_owned"),
        ("OUTSIDE_COLLABORATOR", "third_party"),
    ],
)
def test_user_owned_app_classification_uses_membership_inventory(
    owner_node_id: str, expected: str
) -> None:
    """Only membership inventory establishes member ownership, not repository access."""
    with duckdb.connect(":memory:") as connection:
        connection.execute("CREATE SCHEMA github_test")
        connection.execute("CREATE TABLE github_test.users (id VARCHAR)")
        connection.execute("CREATE TABLE github_test.enterprise_users (id VARCHAR)")
        connection.execute("INSERT INTO github_test.users VALUES ('USER_ORG')")
        connection.execute(
            "INSERT INTO github_test.enterprise_users VALUES ('USER_ENTERPRISE')"
        )
        connection.execute(
            "CREATE TABLE github_test.repo_role_assignments (node_id VARCHAR)"
        )
        connection.execute(
            "INSERT INTO github_test.repo_role_assignments "
            "VALUES ('OUTSIDE_COLLABORATOR')"
        )
        app = _app(_owner("User", owner_node_id))
        app._lookup = GithubLookup(connection, schema="github_test")

        assert app.as_node.properties.registration_origin == expected


def test_org_owned_app_classification_does_not_require_enterprise_lookup() -> None:
    """Organization-only classification depends on organization ownership evidence."""
    app = _app(_owner("Organization", "EXTERNAL_ORG"))
    lookup = MagicMock()
    lookup.is_tenant_organization_node_id.return_value = False
    lookup.enterprise_id.side_effect = AssertionError("Unexpected enterprise lookup")
    app._lookup = lookup

    assert app.as_node.properties.registration_origin == "third_party"


def test_app_with_missing_owner_has_unknown_registration_origin() -> None:
    app = _app(None)

    properties = app.as_node.properties

    assert properties.owner_login is None
    assert properties.owner_node_id is None
    assert properties.owner_type is None
    assert properties.registration_origin == "unknown"


@pytest.mark.parametrize(
    ("owner_type", "owner_node_id"),
    [
        ("Organization", "ORG_NODE_1"),
        ("Enterprise", "ENT_NODE_1"),
        ("User", "USER_NODE_1"),
    ],
)
def test_app_emits_registration_edge_for_collected_owner(
    owner_type: str, owner_node_id: str
) -> None:
    app = _app(_owner(owner_type, owner_node_id))
    lookup = MagicMock()
    lookup.is_tenant_organization_node_id.return_value = True
    lookup.enterprise_id.return_value = owner_node_id
    lookup.is_collected_user_node_id.return_value = True
    app._lookup = lookup

    edge = app.edges[0]

    assert edge.kind == "GH_Owns"
    assert edge.start.value == owner_node_id
    assert edge.end.value == "APP_NODE_123"
    assert edge.properties.traversable is True


def test_app_skips_registration_edge_for_uncollected_owner() -> None:
    app = _app(_owner("Organization", "EXTERNAL_ORG"))
    lookup = MagicMock()
    lookup.is_tenant_organization_node_id.return_value = False
    app._lookup = lookup

    assert app.edges == []
