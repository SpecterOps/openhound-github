import inspect
from unittest.mock import MagicMock

import pytest
from openhound.core.models.entries_dataclass import ConditionalEdgePath

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models import (
    EnterpriseTeam,
    ScimGroup,
    ScimOrganization,
    ScimUser,
)
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise,
    iter_enterprise_scim_resources,
)


def _scim_user(*, legacy: bool = False) -> ScimUser:
    return ScimUser(
        id="scim-user-1",
        externalId="00u-okta-1",
        userName="alice@example.test",
        displayName="Alice Example",
        name={"givenName": "Alice", "familyName": "Example"},
        emails=[{"value": "alice@example.test", "primary": True}],
        active=True,
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
        emit_legacy_correlation=legacy,
    )


def test_enterprise_scim_users_use_enterprise_endpoint_and_scim_pagination() -> None:
    client = MagicMock()
    client.paginate.return_value = [[{"id": "u1"}], [{"id": "u2"}]]

    rows = list(
        iter_enterprise_scim_resources(client, "example-enterprise", "Users")
    )

    assert rows == [{"id": "u1"}, {"id": "u2"}]
    args, kwargs = client.paginate.call_args
    assert args[0] == "/scim/v2/enterprises/example-enterprise/Users"
    assert kwargs["params"] == {"startIndex": 1, "count": 100}
    assert kwargs["data_selector"] == "Resources"
    assert kwargs["paginator"].param_name == "startIndex"
    assert kwargs["paginator"].initial_value == 1
    assert kwargs["paginator"].limit_param == "count"


def test_enterprise_scim_groups_use_groups_companion_endpoint() -> None:
    client = MagicMock()
    client.paginate.return_value = [[]]

    list(iter_enterprise_scim_resources(client, "example-enterprise", "Groups"))

    assert client.paginate.call_args.args[0].endswith(
        "/example-enterprise/Groups"
    )


def test_enterprise_root_fails_loud_when_credentials_cannot_see_scope() -> None:
    client = MagicMock()
    client.paginate.return_value = [[{"enterprise": None}]]
    ctx = SourceContext(client=client, enterprise_name="hidden-enterprise")

    with pytest.raises(RuntimeError, match="did not return enterprise"):
        list(inspect.unwrap(enterprise._pipe.gen)(ctx))


def test_scim_user_emits_normalized_edges_without_legacy_correlation_by_default() -> None:
    user = _scim_user()

    node = user.as_node
    edges = list(user.edges)

    assert node.kinds == [nk.SCIM_USER]
    assert node.properties.environmentid == "ENT_NODE_1"
    assert node.properties.external_id == "00u-okta-1"
    assert [edge.kind for edge in edges] == [
        ek.SCIM_CONTAINS,
        ek.SCIM_PROVISIONED,
    ]
    assert isinstance(edges[1].end, ConditionalEdgePath)
    assert edges[1].end.kind == nk.EXTERNAL_IDENTITY
    assert edges[1].end.property_matchers[0].key == "guid"
    assert edges[1].end.property_matchers[0].value == "scim-user-1"


def test_scim_user_legacy_idp_correlation_is_explicitly_gated() -> None:
    edges = list(_scim_user(legacy=True).edges)

    legacy_edge = edges[-1]
    assert legacy_edge.kind == ek.SCIM_PROVISIONED
    assert legacy_edge.start.value == "00u-okta-1"
    assert legacy_edge.end.value == "scim-user-1"
    assert legacy_edge.properties.traversable is True


def test_scim_user_preserves_emu_rows_without_username() -> None:
    user = ScimUser(
        id="scim-user-without-username",
        externalId="00u-okta-2",
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )

    node = user.as_node

    assert node.properties.user_name is None
    assert node.properties.displayname == "scim-user-without-username"


def test_scim_group_emits_membership_without_speculative_team_edges() -> None:
    group = ScimGroup(
        id="scim-group-1",
        externalId="00g-okta-1",
        displayName="Engineering",
        members=[{"value": "scim-user-1"}, {"value": "scim-user-2"}],
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )

    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [
        ek.SCIM_CONTAINS,
        ek.SCIM_MEMBER_OF,
        ek.SCIM_MEMBER_OF,
    ]
    assert edges[1].start.value == "scim-user-1"


def test_enterprise_team_emits_scim_edge_only_with_group_id_evidence() -> None:
    team = EnterpriseTeam(
        id=7,
        name="Engineering",
        slug="engineering",
        group_id="scim-group-1",
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )
    lookup = MagicMock()
    lookup.enterprise_id.return_value = "ENT_NODE_1"
    team._lookup = lookup

    edges = list(team.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS, ek.SCIM_PROVISIONED]
    assert edges[1].start.value == "scim-group-1"


def test_scim_group_legacy_correlation_matches_githound_okta_name_contract() -> None:
    group = ScimGroup(
        id="scim-group-1",
        externalId="Engineering",
        displayName="Engineering",
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
        emit_legacy_correlation=True,
    )

    edge = list(group.edges)[-1]

    assert edge.kind == ek.SCIM_PROVISIONED
    assert isinstance(edge.start, ConditionalEdgePath)
    assert edge.start.kind == "Okta_Group"
    assert edge.start.property_matchers[0].key == "name"
    assert edge.start.property_matchers[0].value == "Engineering"


def test_scim_organization_stays_within_github_environment_root() -> None:
    organization = ScimOrganization(
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )

    node = organization.as_node

    assert node.id == "SCIM_Organization_ENT_NODE_1"
    assert node.kinds == [nk.SCIM_ORGANIZATION]
    assert node.properties.environmentid == "ENT_NODE_1"
