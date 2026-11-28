from role_id_helpers import configure_role_ids, org_role_id
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
    role = OrgRole(
        id=1,
        name=name,
        type=role_type,
        base_role="admin",
        created_at=datetime.now(),
        org_node_id=org_node_id,
        org_login=org_login,
    )

    role._lookup = configure_role_ids(MagicMock())
    return role


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

    member._lookup = team._lookup = role._lookup
    assert role.name == "Custom Role Manager"
    assert role.node_id == org_role_id("Custom Role Manager")
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
    assignment._lookup = role._lookup
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


@pytest.mark.parametrize(
    "base,permissions,expected",
    [
        (None, ["manage_webhooks"], True),
        (None, ["read_repo_contents"], True),
        ("read", [], False),
        ("triage", [], False),
        ("write", [], False),
        ("maintain", [], False),
        ("admin", [], False),
        ("moderate", [], False),
        ("write", ["manage_webhooks"], True),
        (None, [], False),
        ("none", [], False),
        (None, ["write_organization_actions_secrets"], False),
        (None, ["unknown_permission"], False),
        ("unknown_role", [], False),
    ],
)
def test_org_repository_scope_requires_direct_grants(base, permissions, expected):
    role = _role("ORG_1", "acme", name="custom", role_type="custom")
    role.base_role = base
    role.permissions = permissions
    edges = list(role._repository_scope_edges)
    assert len(edges) == int(expected)
    if expected:
        edge = edges[0]
        assert edge.kind == ek.CAN_ACCESS
        assert edge.start.value == role.node_id
        assert edge.end.value == "GH_Scope_ORG_1_repository_all"
        assert edge.properties.traversable is False


def test_org_owners_without_explicit_repository_grants_have_no_scope_edge():
    role = _role("ORG_1", "acme")
    role.base_role = None
    assert role.as_node.properties.permissions_repository == []
    assert list(role._repository_scope_edges) == []
    role.type = "custom"  # A custom role named owners does not acquire authority.
    assert list(role._repository_scope_edges) == []


def test_all_repository_predefined_role_keeps_inheritance_without_scope_edge():
    role = _role("ORG_2", "example", name="all_repo_write", role_type="custom")
    role.source = "Predefined"
    role.permissions = []
    role.base_role = "write"
    assert role.as_node.properties.permissions_repository == []
    assert list(role._repository_scope_edges) == []
    assert any(e.kind == ek.HAS_BASE_ROLE for e in role.edges)


def test_repository_scope_edge_is_included_in_org_role_output():
    role = _role("ORG_1", "acme", name="custom", role_type="custom")
    role.permissions = ["manage_webhooks"]
    edges = list(role.edges)
    assert {e.end.value for e in edges if e.kind == ek.CAN_ACCESS} == {
        "ORG_1",
        "GH_Scope_ORG_1_repository_all",
    }
    assert any(e.kind == ek.HAS_BASE_ROLE for e in edges)
