from datetime import datetime

from openhound_github.models.org_role import OrgRole
from openhound_github.models.org_role_member import OrgRoleMember
from openhound_github.models.org_role_team import OrgRoleTeam


def _role(
    org_node_id: str, org_login: str, name: str = "owners", role_type: str = "default"
) -> OrgRole:
    return OrgRole(
        id=1,
        name=name,
        type=role_type,
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


def test_custom_org_role_uses_role_only_name_for_assignment_node_ids() -> None:
    role = _role("ORG_1", "acme", name="Custom Role Manager", role_type="custom")
    member = OrgRoleMember(
        id=1,
        node_id="USER_1",
        login="alice",
        type="User",
        site_admin=False,
        org_role_id=role.id,
        org_role_name=role.name,
        org_node_id=role.org_node_id,
        org_login=role.org_login,
    )
    team = OrgRoleTeam(
        id=2,
        node_id="TEAM_1",
        url="https://api.github.com/teams/2",
        name="security",
        slug="security",
        description="Security team",
        permission="pull",
        members_url="https://api.github.com/teams/2/members{/member}",
        repositories_url="https://api.github.com/teams/2/repos",
        org_role_id=role.id,
        org_role_name=role.name,
        org_node_id=role.org_node_id,
        org_login=role.org_login,
    )

    assert role.name == "Custom Role Manager"
    assert role.node_id == "ORG_1_Custom Role Manager"
    assert role.as_node.properties.name == "acme/Custom Role Manager"
    assert member.org_role_node_id == role.node_id
    assert team.org_role_node_id == role.node_id
