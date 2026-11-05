from pathlib import Path
import json

import dlt
import pytest

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models import Enterprise, OidcProvider
from openhound_github.resources.enterprise import (
    SourceContext,
    enterprise_oidc_provider,
    enterprise_saml_provider,
    enterprise_resources,
)
from test_enterprise_resources import _FakeClient, _FailingPostClient


def _enterprise():
    """Build the enterprise fixture used by provider resource tests."""
    return Enterprise(id="E_1", name="Acme", slug="acme")


def _payload():
    """Build the GraphQL response for a configured enterprise OIDC provider."""
    return {
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
    }


def test_oidc_provider_uses_pat_graphql_client_and_converts():
    """Collect provider metadata through the PAT and verify its graph representation."""
    app = _FakeClient({})
    pat = _FakeClient({})
    pat_graphql = _FakeClient(_payload())
    ctx = SourceContext(
        client=app,
        sso_client=pat,
        sso_graphql_client=pat_graphql,
        enterprise_name="acme",
        github_deployment_id="deployment-1",
        github_web_origin="https://github.example.test",
    )
    source = dlt.resource([_enterprise()], name="test_enterprise")
    providers = list(source | enterprise_oidc_provider(ctx))
    assert len(providers) == 1
    provider = providers[0]
    assert isinstance(provider, OidcProvider)
    node = provider.as_node
    assert node.kinds == [nk.OIDC_IDENTITY_PROVIDER, nk.IDENTITY_PROVIDER, "GitHub"]
    assert node.properties.environmentid == "E_1"
    assert node.properties.tenant_id == "tenant-1"
    assert node.properties.provider_type == "AAD"
    assert node.properties.github_deployment_id == "deployment-1"
    assert node.properties.github_web_origin == "https://github.example.test"
    (edge,) = list(provider.edges)
    assert edge.kind == ek.HAS_OIDC_IDENTITY_PROVIDER
    assert edge.start.value == "E_1"
    assert edge.end.value == "OIDC_1"
    assert edge.properties.traversable is False
    assert pat_graphql.post_calls[0][0] == ""
    assert "oidcProvider" in pat_graphql.post_calls[0][1]["query"]
    assert app.post_calls == pat.post_calls == []


@pytest.mark.parametrize(
    "payload,diagnostic",
    [
        (
            {"data": {"enterprise": {"ownerInfo": {"oidcProvider": None}}}},
            "No enterprise OIDC provider configured",
        ),
        ({"data": {"enterprise": None}}, "No enterprise object returned"),
        ({"errors": [{"message": "Forbidden"}]}, "Forbidden"),
        (
            {"errors": [{"message": "Field 'oidcProvider' doesn't exist"}]},
            "doesn't exist",
        ),
    ],
)
def test_absent_or_inaccessible_provider_is_skipped(payload, diagnostic, caplog):
    """Skip absent or inaccessible OIDC providers with a diagnostic."""
    ctx = SourceContext(
        client=None, sso_client=_FakeClient(payload), enterprise_name="acme"
    )
    with caplog.at_level("INFO", logger="openhound_github.resources.enterprise"):
        rows = list(enterprise_oidc_provider.__wrapped__(_enterprise(), ctx))
    assert rows == []
    assert diagnostic in caplog.text


def test_oidc_network_failure_does_not_prevent_saml_collection(caplog):
    """Keep SAML collection available after an OIDC request fails."""
    ctx = SourceContext(
        client=None, sso_client=_FailingPostClient({}), enterprise_name="acme"
    )
    assert list(enterprise_oidc_provider.__wrapped__(_enterprise(), ctx)) == []
    assert "enterprise_oidc_provider" in caplog.text
    saml_client = _FakeClient(
        {
            "data": {
                "enterprise": {
                    "ownerInfo": {
                        "samlIdentityProvider": {"id": "SAML_1"},
                    }
                }
            }
        }
    )
    ctx.sso_client = saml_client
    saml = list(enterprise_saml_provider.__wrapped__(_enterprise(), ctx))
    assert saml[0]["id"] == "SAML_1"
    assert "oidcProvider" not in saml_client.post_calls[0][1]["query"]


def test_oidc_resources_require_pat_and_no_pat_skips_calls():
    """Register and query OIDC resources only when a supplemental PAT exists."""
    app = _FakeClient({})
    ctx = SourceContext(client=app, enterprise_name="acme")
    assert list(enterprise_oidc_provider.__wrapped__(_enterprise(), ctx)) == []
    assert app.post_calls == []
    assert "enterprise_oidc_provider" not in {r.name for r in enterprise_resources(ctx)}
    ctx.sso_client = _FakeClient({})
    resource = next(
        r for r in enterprise_resources(ctx) if r.name == "enterprise_oidc_provider"
    )
    assert resource.table_name == "oidc_provider"


def test_provider_schema_registers_specific_display_kind_and_secondary_kind():
    """Register OIDC display metadata and the shared identity-provider kind."""
    schema = json.loads(
        (Path(__file__).parents[1] / "extension/schema.json").read_text()
    )
    kinds = {n["name"]: n for n in schema["node_kinds"]}
    assert kinds[nk.IDENTITY_PROVIDER]["is_display_kind"] is False
    assert kinds[nk.OIDC_IDENTITY_PROVIDER]["is_display_kind"] is True
    edge = next(
        e
        for e in schema["relationship_kinds"]
        if e["name"] == ek.HAS_OIDC_IDENTITY_PROVIDER
    )
    assert edge["is_traversable"] is False
