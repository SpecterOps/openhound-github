from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openhound_github.kinds import edges as ek
from openhound_github.models.enterprise_role import (
    ENTERPRISE_PERMISSION_EDGES,
    EnterpriseRole,
)
from openhound_github.models.enterprise_user import EnterpriseUser
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_role_teams,
    enterprise_role_users,
    enterprise_roles,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict | None = None):
        self.payload = payload or {"roles": []}
        self.get_calls: list[str] = []
        self.paginate_calls: list[tuple[str, dict]] = []

    def get(self, path: str):
        self.get_calls.append(path)
        return _FakeResponse(self.payload)

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter([])


def _role(permissions: list[str]) -> EnterpriseRole:
    role = EnterpriseRole(
        id=42,
        name="security-manager",
        source="Organization",
        permissions=permissions,
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )
    lookup = MagicMock()
    lookup.enterprise_id.return_value = "ENT_NODE_1"
    role._lookup = lookup
    return role


@pytest.mark.parametrize(
    ("permission", "edge_kind", "traversable"),
    [
        ("manage_enterprise_admins", ek.MANAGE_ENTERPRISE_ADMINS, True),
        ("manage_enterprise_members", ek.MANAGE_ENTERPRISE_MEMBERS, True),
        (
            "manage_enterprise_organization_admins",
            ek.MANAGE_ENTERPRISE_ORGANIZATION_ADMINS,
            True,
        ),
        ("write_enterprise_sso", ek.WRITE_ENTERPRISE_SSO, False),
        (
            "create_enterprise_organizations",
            ek.CREATE_ENTERPRISE_ORGANIZATIONS,
            False,
        ),
    ],
)
def test_enterprise_permissions_become_capability_edges(
    permission: str,
    edge_kind: str,
    traversable: bool,
) -> None:
    edges = list(_role([permission]).edges)

    capability = edges[1]
    assert capability.kind == edge_kind
    assert capability.end.value == "ENT_NODE_1"
    assert capability.properties.traversable is traversable


def test_every_enterprise_permission_has_a_unique_edge_kind() -> None:
    assert len(ENTERPRISE_PERMISSION_EDGES) == 23
    assert len({kind for kind, _ in ENTERPRISE_PERMISSION_EDGES.values()}) == 23


def test_unknown_enterprise_permission_is_preserved_but_not_invented_as_edge() -> None:
    edges = list(_role(["future_permission_not_yet_modeled"]).edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS]


def test_every_enterprise_user_receives_builtin_members_role() -> None:
    user = EnterpriseUser(
        id="USER_NODE_1",
        login="alice",
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
        has_direct_enterprise_membership=False,
    )
    lookup = MagicMock()
    lookup.enterprise_id.return_value = "ENT_NODE_1"
    user._lookup = lookup

    edges = list(user.edges)

    assert [edge.kind for edge in edges] == [ek.HAS_ROLE]
    assert edges[0].end.value.endswith("_members")


def test_enterprise_roles_include_synthetic_members_role() -> None:
    client = _FakeClient({"roles": []})
    ctx = SourceContext(client=client, enterprise_name="example-enterprise")

    rows = list(enterprise_roles.__wrapped__(SimpleNamespace(id="ENT_NODE_1"), ctx))

    assert [row["id"] for row in rows] == ["owners", "members"]


@pytest.mark.parametrize("transformer", [enterprise_role_users, enterprise_role_teams])
def test_synthetic_enterprise_roles_do_not_call_assignment_endpoints(transformer) -> None:
    client = _FakeClient()
    ctx = SourceContext(client=client, enterprise_name="example-enterprise")
    role = _role([])
    role.id = "members"

    assert list(transformer.__wrapped__(role, ctx)) == []
    assert client.paginate_calls == []
