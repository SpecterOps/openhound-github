from datetime import datetime

from openhound_github.models.org_role import OrgRole


def _role(org_node_id: str, org_login: str) -> OrgRole:
    return OrgRole(
        id=1,
        name="owners",
        type="default",
        base_role="admin",
        created_at=datetime.now(),
        org_node_id=org_node_id,
        org_login=org_login,
    )


def test_org_role_name_is_qualified_by_organization() -> None:
    acme_role = _role("ORG_1", "acme")
    example_role = _role("ORG_2", "example")

    assert acme_role.as_node.properties.name == "acme/owners"
    assert acme_role.as_node.properties.displayname == "acme/owners"
    assert acme_role.as_node.properties.short_name == "owners"

    assert example_role.as_node.properties.name == "example/owners"
    assert example_role.as_node.properties.displayname == "example/owners"
    assert example_role.as_node.properties.short_name == "owners"
