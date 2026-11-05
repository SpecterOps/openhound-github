import gzip
import json
from types import SimpleNamespace

import dlt
import duckdb
import pytest
from openhound.core.progress import Progress

from openhound_github.graphql import ENTERPRISE_OIDC_QUERY, ENTERPRISE_SAML_QUERY
from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.main import preproc
from openhound_github.models import Enterprise, ExternalIdentity
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_external_identity,
    enterprise_oidc_external_identity,
    enterprise_oidc_provider,
)
from openhound_github.transforms import ensure_optional_input_tables
from test_enterprise_resources import _FakeClient, _FailingPaginateClient


def _identity_record(i=1):
    return {
        "id": f"EI_{i}",
        "guid": f"guid-{i}",
        "samlIdentity": None,
        "scimIdentity": {"username": f"user{i}@example.test"},
        "user": {"id": f"U_{i}", "login": f"user{i}_acme"},
    }


@pytest.mark.parametrize("provider_field", ["samlIdentityProvider", "oidcProvider"])
def test_shared_identity_collection_reads_all_pages_and_preserves_fields(
    provider_field,
):
    pages = [
        [
            {
                "enterprise": {
                    "ownerInfo": {
                        provider_field: {
                            "externalIdentities": {
                                "nodes": [None, _identity_record(i)]
                            },
                        }
                    }
                }
            }
        ]
        for i in (1, 2)
    ]
    app = _FakeClient({})
    pat = _FakeClient({}, pages=pages)
    ctx = SourceContext(client=app, sso_client=pat, enterprise_name="acme")
    if provider_field == "samlIdentityProvider":
        records = enterprise_external_identity.__wrapped__(
            {"environment_slug": "acme", "github_deployment_id": "deployment-1"},
            ctx,
        )
    else:
        records = enterprise_oidc_external_identity.__wrapped__(
            SimpleNamespace(
                environment_slug="acme", github_deployment_id="deployment-1"
            ),
            ctx,
        )
    rows = list(records)
    assert [r["id"] for r in rows] == ["EI_1", "EI_2"]
    assert rows[0] == {
        **_identity_record(),
        "environment_slug": "acme",
        "github_deployment_id": "deployment-1",
    }
    assert app.paginate_calls == []
    path, request = pat.paginate_calls[0]
    assert path == "/graphql"
    assert (
        request["paginator"].page_info_path
        == f"data.enterprise.ownerInfo.{provider_field}.externalIdentities.pageInfo"
    )
    expected = (
        ENTERPRISE_SAML_QUERY
        if provider_field == "samlIdentityProvider"
        else ENTERPRISE_OIDC_QUERY
    )
    assert request["json"]["query"] == expected


def test_oidc_extraction_pipeline_validates_provider_and_shares_identity_table():
    pat = _FakeClient(
        {
            "data": {
                "enterprise": {
                    "ownerInfo": {
                        "oidcProvider": {
                            "id": "OIDC_1",
                            "providerType": "AAD",
                            "tenantId": "tenant-1",
                        }
                    }
                }
            }
        },
        pages=[
            [
                {
                    "enterprise": {
                        "ownerInfo": {
                            "oidcProvider": {
                                "externalIdentities": {"nodes": [_identity_record()]},
                            }
                        }
                    }
                }
            ]
        ],
    )
    ctx = SourceContext(client=None, sso_client=pat, enterprise_name="acme")
    source = dlt.resource(
        [Enterprise(id="E_1", name="Acme", slug="acme")], name="test_enterprise"
    )
    resource = (
        source | enterprise_oidc_provider(ctx) | enterprise_oidc_external_identity(ctx)
    )
    rows = list(resource)
    assert resource.table_name == "external_identities"
    assert rows[0]["environment_slug"] == "acme"
    assert (
        ExternalIdentity.model_validate(rows[0]).scim_identity.username
        == "user1@example.test"
    )


def test_oidc_pagination_failure_is_diagnostic_and_returns(caplog):
    ctx = SourceContext(
        client=None, sso_client=_FailingPaginateClient({}), enterprise_name="acme"
    )
    rows = list(
        enterprise_oidc_external_identity.__wrapped__(
            SimpleNamespace(environment_slug="acme", github_deployment_id="github.com"),
            ctx,
        )
    )
    assert rows == []
    assert "enterprise_oidc_external_identity" in caplog.text


def _write_records(root, table, rows):
    directory = root / table
    directory.mkdir()
    with gzip.open(directory / "rows.jsonl.gz", "wt") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


@pytest.mark.parametrize("federation", ["saml", "oidc"])
def test_preprocessing_and_conversion_resolve_provider_without_identity_properties(
    tmp_path, federation
):
    provider = {
        "id": "IDP_1",
        "environment_node_id": "E_1",
        "environment_name": "Acme",
        "environment_slug": "acme",
    }
    if federation == "saml":
        provider.update(
            environment_type="enterprise",
            issuer="https://idp.example.test",
            sso_url="https://idp.example.test/sso",
        )
    else:
        provider.update(provider_type="AAD", tenant_id="tenant-1")
    _write_records(tmp_path, f"{federation}_provider", [provider])
    _write_records(
        tmp_path,
        "external_identities",
        [{**_identity_record(), "environment_slug": "acme"}],
    )
    database = tmp_path / "lookup.duckdb"
    preproc(tmp_path, database, progress=Progress.log)
    connection = duckdb.connect(str(database))
    lookup = GithubLookup(connection)
    identity = ExternalIdentity.model_validate(
        {**_identity_record(), "environment_slug": "acme"}
    )
    identity._lookup = lookup
    assert identity.as_node.properties.environmentid == "E_1"
    assert identity.as_node.properties.environment_name == "Acme"
    assert not hasattr(identity.as_node.properties, "provider_id")
    edges = list(identity.edges)
    provider_edge = next(e for e in edges if e.kind == ek.HAS_EXTERNAL_IDENTITY)
    assert provider_edge.start.value == "IDP_1"
    assert provider_edge.end.value == "EI_1"
    assert all(e.properties.traversable is False for e in edges)
    assert any(e.kind == ek.MAPS_TO_USER and e.end.value == "U_1" for e in edges)
    assert (ek.SAML_HAS_ACCOUNT in {e.kind for e in edges}) == (federation == "saml")
    connection.close()


@pytest.mark.parametrize("user", [None, {"id": "U_1", "login": "user1_acme"}])
def test_nullable_identity_attributes_and_unlinked_user_are_retained(user):
    identity = ExternalIdentity(
        id="EI_1",
        guid="guid-1",
        environment_slug="acme",
        samlIdentity=None,
        scimIdentity=None,
        user=user,
    )
    identity._lookup = SimpleNamespace(
        identity_providers_for_environment=lambda _: [
            ("OIDC_1", None, None, "E_1", "Acme", "enterprise", "oidc"),
        ]
    )
    assert identity.as_node.properties.name == "guid-1"
    edges = list(identity.edges)
    assert edges[0].kind == ek.HAS_EXTERNAL_IDENTITY
    assert (ek.MAPS_TO_USER in {e.kind for e in edges}) == bool(user)
    assert ek.SAML_HAS_ACCOUNT not in {e.kind for e in edges}


def test_oidc_does_not_emit_saml_edge_even_if_saml_attributes_are_present():
    identity = ExternalIdentity.model_validate(
        {
            **_identity_record(),
            "environment_slug": "acme",
            "samlIdentity": {"nameId": "name-id"},
        }
    )
    identity._lookup = SimpleNamespace(
        identity_providers_for_environment=lambda _: [
            ("OIDC_1", None, None, "E_1", "Acme", "enterprise", "oidc"),
        ]
    )
    assert ek.SAML_HAS_ACCOUNT not in {e.kind for e in identity.edges}


def test_missing_or_ambiguous_provider_does_not_emit_invalid_association(caplog):
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    ensure_optional_input_tables(connection)
    connection.execute(
        "INSERT INTO github.saml_provider VALUES ('SAML_1', NULL, NULL, 'E_1', 'Acme', 'enterprise', 'acme')"
    )
    connection.execute(
        "INSERT INTO github.oidc_provider VALUES ('OIDC_1', 'E_1', 'Acme', 'acme')"
    )
    lookup = GithubLookup(connection)
    for slug in ("missing", "acme"):
        identity = ExternalIdentity.model_validate(
            {**_identity_record(), "environment_slug": slug}
        )
        identity._lookup = lookup
        assert [e.kind for e in identity.edges] == [ek.MAPS_TO_USER]
    assert "ambiguous provider association" in caplog.text
    connection.close()
