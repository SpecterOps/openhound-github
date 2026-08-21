import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
from openhound.core.models.entries_dataclass import ConditionalEdgePath
from openhound.core.progress import Progress

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.lookup import GithubLookup
from openhound_github.main import preproc
from openhound_github.models import EnterpriseTeam, ScimGroup, ScimOrganization, ScimUser
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
            f.write(json.dumps(row))
            f.write("\n")

    lookup_file = tmp_path / "lookup.duckdb"
    preproc(tmp_path, lookup_file, progress=Progress.log)
    return GithubLookup(duckdb.connect(str(lookup_file)))


def test_enterprise_scim_uses_enterprise_endpoint_and_scim_pagination() -> None:
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

    assert node.kinds == [nk.SCIM_USER]
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
    assert node.kinds == [nk.SCIM_ORGANIZATION]
    assert node.properties.environmentid == "ENT_NODE_1"


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
