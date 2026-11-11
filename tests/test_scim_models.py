import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest
from openhound.core.models.entries_dataclass import ConditionalEdgePath
from openhound.core.progress import Progress
from openhound.sources.opengraph.entries import GraphContent
from openhound.sources.opengraph.source import _generate_graph_content

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.lookup import GithubLookup
from openhound_github.main import preproc
from openhound_github.models import (
    EnterpriseTeam,
    ScimGroup,
    ScimOrganization,
    ScimUser,
)
from openhound_github.resources.enterprise import iter_enterprise_scim_resources


def _scim_user(*, legacy: bool = False, user_id: str = "scim-user-1") -> ScimUser:
    return ScimUser(
        id=user_id,
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


def _external_identity_lookup(tmp_path: Path) -> GithubLookup:
    resource_dir = tmp_path / "external_identities"
    resource_dir.mkdir()
    with gzip.open(resource_dir / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in [
            {
                "id": "external-identity-wrong-guid",
                "guid": "scim-user-2",
                "environment_slug": "example-enterprise",
            },
            {
                "id": "external-identity-wrong-scope",
                "guid": "scim-user-1",
                "environment_slug": "other-enterprise",
            },
            {
                "id": "external-identity-1",
                "guid": "scim-user-1",
                "environment_slug": "example-enterprise",
            },
        ]:
            row["environment_node_id"] = (
                "OTHER_ENT"
                if row["environment_slug"] == "other-enterprise"
                else "ENT_NODE_1"
            )
            f.write(json.dumps(row))
            f.write("\n")

    lookup_file = tmp_path / "lookup.duckdb"
    preproc(tmp_path, lookup_file, progress=Progress.log)
    return GithubLookup(duckdb.connect(str(lookup_file)))


def test_enterprise_scim_uses_enterprise_endpoint_and_scim_pagination() -> None:
    client = MagicMock()
    client.paginate.return_value = [[{"id": "u1"}], [{"id": "u2"}]]

    rows = list(iter_enterprise_scim_resources(client, "example-enterprise", "Users"))

    assert rows == [{"id": "u1"}, {"id": "u2"}]
    args, kwargs = client.paginate.call_args
    assert args[0] == "/scim/v2/enterprises/example-enterprise/Users"
    assert kwargs["params"] == {"startIndex": 1, "count": 100}
    assert kwargs["data_selector"] == "Resources"
    assert kwargs["paginator"].param_name == "startIndex"
    assert kwargs["paginator"].initial_value == 1
    assert kwargs["paginator"].limit_param == "count"


def test_scim_user_emits_normalized_edges_without_legacy_correlation_by_default(
    tmp_path: Path,
) -> None:
    lookup = _external_identity_lookup(tmp_path)
    user = _scim_user()
    user._lookup = lookup
    unmatched_user = _scim_user(user_id="scim-user-missing")
    unmatched_user._lookup = lookup

    node = user.as_node
    edges = list(user.edges)
    unmatched_edges = list(unmatched_user.edges)

    assert node.kinds == [nk.SCIM_USER, "SCIM"]
    assert node.properties.environmentid == "ENT_NODE_1"
    assert node.properties.external_id == "00u-okta-1"
    assert node.properties.name == "alice@example.test"
    assert node.properties.user_name == "alice@example.test"
    assert [edge.kind for edge in edges] == [
        ek.SCIM_CONTAINS,
        ek.SCIM_PROVISIONED,
    ]
    assert edges[1].end.value == "external-identity-1"
    assert edges[1].end.match_by == "id"
    assert [edge.kind for edge in unmatched_edges] == [ek.SCIM_CONTAINS]


def test_scim_user_legacy_idp_correlation_is_explicitly_gated(tmp_path: Path) -> None:
    user = _scim_user(legacy=True)
    user._lookup = _external_identity_lookup(tmp_path)

    edges = list(user.edges)

    legacy_edge = edges[-1]
    assert legacy_edge.kind == ek.SCIM_PROVISIONED
    assert legacy_edge.start.value == "00u-okta-1"
    assert legacy_edge.end.value == "scim-user-1"
    assert legacy_edge.properties.traversable is True


@pytest.mark.parametrize(
    "scope",
    [
        {"enterprise_node_id": "ENT_NODE_1", "enterprise_slug": "example-enterprise"},
        {"org_node_id": "ORG_NODE_1", "org_login": "example-org"},
    ],
)
def test_scim_user_preserves_metadata_roles_and_groups_in_graph_output(scope) -> None:
    roles = [
        {"value": "enterprise_owner", "display": "Owner", "primary": True},
        {"value": "custom-role", "type": "custom", "extra": {"source": "IdP"}},
    ]
    groups = [
        {
            "value": "scim-group-1",
            "display": "Engineering",
            "$ref": "https://api.github.com/scim/v2/Groups/scim-group-1",
        },
        {"value": "scim-group-2", "type": "direct"},
    ]
    resource = {
        "id": "scim-user-1",
        "externalId": "foreign-user-1",
        "userName": "alice@example.test",
        "profileUrl": "https://github.com/alice",
        "active": True,
        "roles": roles,
        "groups": groups,
        "meta": {
            "location": "https://api.github.com/scim/v2/Users/scim-user-1",
            "created": "2026-01-01T10:00:00Z",
            "lastModified": "2026-02-01T11:00:00Z",
        },
        **scope,
    }
    lookup = MagicMock()
    lookup.external_identity_id_for_guid.return_value = None
    lookup.scim_group_has_member.return_value = False

    def apply_context(user):
        user._lookup = lookup

    entries = list(_generate_graph_content([resource], ScimUser, 150, apply_context))
    # Validate through the converter's output model, including JSON serialization.
    node = json.loads(GraphContent(**entries[0]).model_dump_json())["graph"]["content"]
    properties = node["properties"]
    assert node["id"] == "scim-user-1"
    assert properties["external_id"] == "foreign-user-1"
    assert properties["active"] is True
    assert properties["enabled"] is True
    assert "externalId" not in properties
    assert properties["environmentid"] == scope.get(
        "enterprise_node_id", scope.get("org_node_id")
    )
    assert properties["profile_url"] == resource["profileUrl"]
    assert properties["resource_url"] == resource["meta"]["location"]
    assert properties["created_at"] == resource["meta"]["created"]
    assert properties["updated_at"] == resource["meta"]["lastModified"]
    assert json.loads(properties["roles"]) == roles
    assert json.loads(properties["groups"]) == groups
    membership_edges = [
        edge
        for entry in entries[1:]
        for edge in entry["graph"]["content"]
        if edge["kind"] == ek.SCIM_MEMBER_OF
    ]
    assert [edge["end"]["value"] for edge in membership_edges] == [
        group["value"] for group in groups
    ]


@pytest.mark.parametrize(
    "meta", [None, {}, {"location": "https://api.github.com/scim/v2/Users/u1"}]
)
def test_scim_user_handles_missing_metadata_without_profile_url_fallback(meta) -> None:
    user = ScimUser(id="u1", org_node_id="ORG_NODE_1", meta=meta)

    properties = user.as_node.properties

    assert properties.profile_url is None
    assert properties.resource_url == (meta or {}).get("location")
    assert properties.created_at is None
    assert properties.updated_at is None
    assert json.loads(properties.roles) == []
    assert json.loads(properties.groups) == []


def test_scim_user_memberships_supplement_group_evidence_without_duplicates(
    tmp_path: Path,
) -> None:
    resource_dir = tmp_path / "enterprise_scim_groups"
    resource_dir.mkdir()
    groups = [
        {
            "id": "shared",
            "displayName": "Shared",
            "members": [{"value": "scim-user-1"}],
            "enterprise_node_id": "ENT_NODE_1",
        },
        {
            "id": "user-only",
            "displayName": "User only",
            "members": [],
            "enterprise_node_id": "ENT_NODE_1",
        },
        {
            "id": "other-scope",
            "displayName": "Other scope",
            "members": [{"value": "scim-user-1"}],
            "enterprise_node_id": "OTHER_ENT",
        },
    ]
    with gzip.open(resource_dir / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
        for group in groups:
            f.write(json.dumps(group) + "\n")
    lookup = _external_identity_lookup(tmp_path)
    user = _scim_user()
    user._lookup = lookup
    user.groups = [
        {"value": "shared"},
        {"value": "user-only"},
        {"value": "user-only"},
        {"value": "uncollected"},
        {"value": "other-scope"},
        {},
        {"value": ""},
    ]

    membership_edges = [edge for edge in user.edges if edge.kind == ek.SCIM_MEMBER_OF]
    assert [edge.end.value for edge in membership_edges] == [
        "user-only",
        "uncollected",
        "other-scope",
    ]
    for edge in membership_edges:
        assert edge.start.value == user.id
        assert edge.start.match_by == edge.end.match_by == "id"
        assert edge.properties.traversable is True

    for raw_group in groups[:2]:
        group = ScimGroup(**raw_group)
        group._lookup = lookup
        membership_edges.extend(
            edge for edge in group.edges if edge.kind == ek.SCIM_MEMBER_OF
        )
    assert [edge.end.value for edge in membership_edges].count("shared") == 1
    assert len(
        {(edge.start.value, edge.end.value) for edge in membership_edges}
    ) == len(membership_edges)


def test_org_scim_user_emits_membership_without_collected_groups(
    tmp_path: Path,
) -> None:
    user = ScimUser(
        id="u1",
        org_node_id="ORG_NODE_1",
        org_login="acme",
        groups=[{"value": "g1"}],
        active=True,
    )
    lookup = _external_identity_lookup(tmp_path)
    user._lookup = lookup
    edges = [edge for edge in user.edges if edge.kind == ek.SCIM_MEMBER_OF]
    assert len(edges) == 1
    assert edges[0].end.value == "g1"


@pytest.mark.parametrize("state", [True, False, None])
@pytest.mark.parametrize("legacy", [False, True])
def test_scim_user_access_edges_require_active_state_but_preserve_evidence(
    state,
    legacy,
) -> None:
    groups = [{"value": "g1", "display": "Engineering"}]
    roles = [{"value": "enterprise_owner", "primary": False}]
    fields = {} if state is None else {"active": state}
    user = ScimUser(
        id="u1",
        org_node_id="ORG_NODE_1",
        groups=groups,
        roles=roles,
        externalId="foreign-user-1",
        emit_legacy_correlation=legacy,
        **fields,
    )
    lookup = MagicMock()
    lookup.scim_group_has_member.return_value = False
    lookup.external_identity_id_for_guid.return_value = "external-identity-1"
    user._lookup = lookup
    properties = user.as_node.properties
    assert properties.active is state
    assert properties.enabled is state
    assert json.loads(properties.groups) == groups
    assert json.loads(properties.roles) == roles
    kinds = [edge.kind for edge in user.edges]
    assert kinds.count(ek.SCIM_MEMBER_OF) == (1 if state is True else 0)
    assert kinds.count(ek.SCIM_CONTAINS) == 1
    assert kinds.count(ek.SCIM_PROVISIONED) == (
        (2 if legacy else 1) if state is True else 0
    )
    if state is not True:
        lookup.scim_group_has_member.assert_not_called()
        lookup.external_identity_id_for_guid.assert_not_called()


def test_scim_group_preserves_metadata_and_count_without_member_array() -> None:
    resource = {
        "id": "scim-group-1",
        "displayName": "Engineering",
        "externalId": "foreign-group-1",
        "enterprise_node_id": "ENT_NODE_1",
        "enterprise_slug": "example-enterprise",
        "members": [{"value": "user-1"}, {"value": "user-2"}],
        "meta": {
            "location": "https://api.github.com/scim/v2/Groups/scim-group-1",
            "created": "2026-01-01T10:00:00Z",
            "lastModified": "2026-02-01T11:00:00Z",
        },
    }
    entries = list(_generate_graph_content([resource], ScimGroup, 150))
    node = json.loads(GraphContent(**entries[0]).model_dump_json())["graph"]["content"]
    properties = node["properties"]
    assert node["id"] == resource["id"]
    assert node["kinds"] == [nk.SCIM_GROUP, "SCIM"]
    assert properties["external_id"] == resource["externalId"]
    assert properties["environmentid"] == resource["enterprise_node_id"]
    assert properties["resource_url"] == resource["meta"]["location"]
    assert properties["created_at"] == resource["meta"]["created"]
    assert properties["updated_at"] == resource["meta"]["lastModified"]
    assert properties["member_count"] == 2
    assert "members" not in properties
    edges = entries[1]["graph"]["content"]
    assert [edge["kind"] for edge in edges] == [
        ek.SCIM_CONTAINS,
        ek.SCIM_MEMBER_OF,
        ek.SCIM_MEMBER_OF,
    ]
    assert [edge["start"]["value"] for edge in edges[1:]] == ["user-1", "user-2"]
    assert all(edge["end"]["value"] == resource["id"] for edge in edges)


@pytest.mark.parametrize(
    "member_fields, expected_count",
    [({}, None), ({"members": None}, None), ({"members": []}, 0)],
)
def test_scim_group_distinguishes_unknown_and_empty_member_lists(
    member_fields, expected_count
) -> None:
    group = ScimGroup(
        id="g1",
        displayName="Engineering",
        enterprise_node_id="ENT_NODE_1",
        **member_fields,
    )
    # Collection serializes the model before graph conversion; retain unknown
    # versus empty membership across that boundary as well.
    converted = ScimGroup(**group.model_dump())
    properties = converted.as_node.properties
    assert properties.member_count == expected_count
    assert properties.resource_url is None
    assert properties.created_at is None
    assert properties.updated_at is None
    assert [edge.kind for edge in converted.edges] == [ek.SCIM_CONTAINS]


def test_scim_group_emits_membership_and_tenant_scoped_legacy_correlation() -> None:
    group = ScimGroup(
        id="scim-group-1",
        externalId="Engineering",
        displayName="Engineering",
        members=[{"value": "scim-user-1"}, {"value": "scim-user-2"}],
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
        emit_legacy_correlation=True,
    )
    lookup = MagicMock()
    lookup.enterprise_idp_for_scope.return_value = (
        "http://www.okta.com/exk-example",
        "https://preview2.example.okta.com/app/github/sso/saml",
    )
    group._lookup = lookup

    edges = list(group.edges)

    assert group.as_node.kinds == [nk.SCIM_GROUP, "SCIM"]
    assert [edge.kind for edge in edges] == [
        ek.SCIM_CONTAINS,
        ek.SCIM_MEMBER_OF,
        ek.SCIM_MEMBER_OF,
        ek.SCIM_PROVISIONED,
    ]
    legacy_edge = edges[-1]
    assert isinstance(legacy_edge.start, ConditionalEdgePath)
    assert {
        matcher.key: matcher.value for matcher in legacy_edge.start.property_matchers
    } == {
        "tenant_domain": "preview2.example.okta.com",
        "name": "ENGINEERING",
    }


def test_enterprise_team_emits_scim_provisioning_edge_with_group_id() -> None:
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


def test_scim_organization_stays_within_github_environment_root() -> None:
    organization = ScimOrganization(
        enterprise_node_id="ENT_NODE_1",
        enterprise_slug="example-enterprise",
    )

    node = organization.as_node

    assert node.id == "SCIM_Organization_ENT_NODE_1"
    assert node.kinds == [nk.SCIM_ORGANIZATION, "SCIM"]
    assert node.properties.environmentid == "ENT_NODE_1"
    assert node.properties.scope_type == "enterprise"
    assert node.properties.scim_base_url is None


@pytest.mark.parametrize(
    "scope, scope_type, scope_id",
    [
        (
            {"enterprise_node_id": "E_CaseSensitive", "enterprise_slug": "acme"},
            "enterprise",
            "E_CaseSensitive",
        ),
        (
            {"org_node_id": "O_CaseSensitive", "org_login": "acme"},
            "organization",
            "O_CaseSensitive",
        ),
    ],
)
def test_scim_organization_exports_endpoint_without_changing_scope(
    scope, scope_type, scope_id
):
    base_url = f"https://api.example.ghe.com/scim/v2/{'enterprises' if scope_type == 'enterprise' else 'organizations'}/acme/"
    resource = {**scope, "scim_base_url": base_url}
    entry = next(_generate_graph_content([resource], ScimOrganization, 150))
    node = json.loads(GraphContent(**entry).model_dump_json())["graph"]["content"]
    assert node["id"] == f"SCIM_Organization_{scope_id}"
    assert node["properties"]["environmentid"] == scope_id
    assert node["properties"]["scope_type"] == scope_type
    assert node["properties"]["scim_base_url"] == base_url


def test_enterprise_idp_lookup_uses_unified_saml_provider_table() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        """CREATE TABLE github.saml_provider (
            environment_node_id VARCHAR,
            environment_type VARCHAR,
            issuer VARCHAR,
            sso_url VARCHAR
        )"""
    )
    connection.execute(
        """INSERT INTO github.saml_provider VALUES
        ('ENT_NODE_1', 'enterprise', 'http://www.okta.com/exk-example',
         'https://preview2.example.okta.com/app/github/sso/saml')"""
    )

    assert GithubLookup(connection).enterprise_idp_for_scope("ENT_NODE_1") == (
        "http://www.okta.com/exk-example",
        "https://preview2.example.okta.com/app/github/sso/saml",
    )
