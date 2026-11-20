from datetime import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from openhound_github.kinds import edges as ek
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


@pytest.fixture
def role_team_payload():
    team = json.loads(
        (Path(__file__).parent / "test_data/api/org-role-teams.json").read_text()
    )[0]
    return {
        **team,
        "org_role_id": 1,
        "org_role_name": "Custom Role Manager",
        "org_node_id": "ORG_1",
        "org_login": "acme",
    }


@pytest.mark.parametrize(
    "description_fields",
    [{"description": None}, {}, {"description": ""}, {"description": "Security team"}],
    ids=["null", "missing", "empty", "populated"],
)
def test_org_role_team_preserves_assignment_with_optional_description(
    role_team_payload, description_fields
):
    from openhound_github.resources.organization import SourceContext, org_role_teams

    role = _role("ORG_1", "acme", name="Custom Role Manager", role_type="custom")
    team_payload = {
        key: value
        for key, value in role_team_payload.items()
        if key
        not in {
            "description",
            "org_role_id",
            "org_role_name",
            "org_node_id",
            "org_login",
        }
    }
    team_payload.update(description_fields)
    client = MagicMock()
    client.paginate.return_value = iter([[team_payload]])

    rows = list(org_role_teams.__wrapped__(role, SourceContext(client=client)))
    assert len(rows) == 1
    assignment = OrgRoleTeam.model_validate(rows[0])
    assert assignment.description == description_fields.get("description")
    assert assignment.as_node is None
    (edge,) = assignment.edges
    assert edge.kind == ek.HAS_ROLE
    assert edge.start.value == role_team_payload["node_id"]
    assert edge.end.value == role.node_id
    assert edge.start.match_by == edge.end.match_by == "id"
    assert edge.properties.traversable is True
    client.paginate.assert_called_once_with("/orgs/acme/organization-roles/1/teams")


@pytest.mark.parametrize(
    "field", ["id", "node_id", "org_role_id", "org_role_name", "org_node_id"]
)
def test_org_role_team_still_requires_assignment_identifiers(role_team_payload, field):
    del role_team_payload[field]
    with pytest.raises(ValidationError) as caught:
        OrgRoleTeam.model_validate(role_team_payload)
    assert any(
        error["loc"] == (field,) and error["type"] == "missing"
        for error in caught.value.errors()
    )
