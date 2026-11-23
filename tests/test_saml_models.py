from types import SimpleNamespace

import pytest
from openhound_saml_producer.contract import EdgeKind

from openhound_github.graphql import ENTERPRISE_SAML_QUERY, SAML_IDENTITIES_QUERY
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.external_identity import ExternalIdentity
from openhound_github.models.saml_assertion_consumer_service import (
    SamlAssertionConsumerService,
)
from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
)
from openhound_github.models.saml_issuer import SamlIssuer
from openhound_github.models.saml_provider import SamlProvider
from openhound_github.models.saml_service_provider import SamlServiceProvider

SAML_HAS_ACCOUNT = EdgeKind.HAS_ACCOUNT.value


def _identity_with_lookup(**overrides) -> ExternalIdentity:
    data = {
        "guid": "guid-1",
        "id": "external-identity-1",
        "environment_slug": "acme",
        "samlIdentity": {
            "username": "Alice@example.com",
            "nameId": "subject-1",
            "attributes": [
                {
                    "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                    "value": "11111111-1111-4111-8111-111111111111",
                }
            ],
        },
        "scimIdentity": {"username": "scim-only@example.com"},
        "user": {"id": "USER_1", "login": "alice"},
    }
    data.update(overrides)
    identity = ExternalIdentity.model_validate(data)
    identity._lookup = SimpleNamespace(
        identity_providers_for_environment=lambda _slug: [
            (
                "IDP_1",
                "https://issuer.example.com",
                "https://issuer.example.com/sso",
                "ORG_1",
                "Acme",
                "org",
                "saml",
            )
        ]
    )
    return identity


def _saml_account_edge(identity: ExternalIdentity):
    return next(edge for edge in identity.edges if edge.kind == SAML_HAS_ACCOUNT)


def test_external_identity_prefers_saml_username_for_display_name() -> None:
    identity = _identity_with_lookup()

    assert identity.as_node.kinds == [nk.EXTERNAL_IDENTITY, "GitHub"]
    assert identity.as_node.properties.name == "Alice@example.com"
    assert identity.as_node.properties.displayname == "Alice@example.com"


def test_external_identity_uses_scim_username_without_saml_identity() -> None:
    identity = _identity_with_lookup(samlIdentity=None)

    assert identity.as_node.properties.name == "scim-only@example.com"
    assert identity.as_node.properties.displayname == "scim-only@example.com"


def test_external_identity_falls_back_to_guid_without_foreign_username() -> None:
    identity = _identity_with_lookup(samlIdentity=None, scimIdentity=None)

    assert identity.as_node.properties.name == "guid-1"
    assert identity.as_node.properties.displayname == "guid-1"


def _scope_assets(**scope):
    """Build the three SAML assets of one organization from one scope."""
    scope = {
        "environment_node_id": "ORG_1",
        "environment_name": "Acme",
        "environment_slug": "acme",
        "environment_type": "org",
        **scope,
    }
    return (
        SamlServiceProvider(
            id="IDP_1", issuer="https://issuer.example.com", **scope
        ),
        SamlIssuer(issuer="https://issuer.example.com", **scope),
        SamlAssertionConsumerService(**scope),
    )


def test_normalized_saml_assets_build_library_nodes_and_edges() -> None:
    service_provider, issuer, acs = _scope_assets()

    sp_node, issuer_node, acs_node = (
        service_provider.as_node,
        issuer.as_node,
        acs.as_node,
    )
    edges = {edge.kind: edge for edge in service_provider.edges}

    assert sp_node.kinds == ["SAML_ServiceProvider", "SAML"]
    assert issuer_node.kinds == ["SAML_Issuer", "SAML"]
    assert acs_node.kinds == ["SAML_AssertionConsumerService", "SAML"]
    assert sp_node.properties.native_object_id == "IDP_1"
    assert sp_node.properties.environmentid == "ORG_1"
    assert sp_node.properties.github_deployment_id == DEFAULT_GITHUB_DEPLOYMENT_ID
    assert sp_node.properties.github_web_origin == DEFAULT_GITHUB_WEB_ORIGIN
    assert issuer_node.properties.entity_id == "https://issuer.example.com"
    assert acs_node.properties.acs_url == "https://github.com/orgs/acme/saml/consume"
    assert acs_node.properties.sp_entity_id == "https://github.com/orgs/acme"

    assert set(edges) == {
        "SAML_Implements",
        "SAML_TrustsIssuer",
        "SAML_HasAssertionConsumerService",
    }
    assert edges["SAML_Implements"].start.value == "IDP_1"
    assert edges["SAML_Implements"].end.value == sp_node.id
    assert edges["SAML_TrustsIssuer"].start.value == sp_node.id
    assert edges["SAML_TrustsIssuer"].end.value == issuer_node.id
    assert edges["SAML_HasAssertionConsumerService"].end.value == acs_node.id
    assert not list(issuer.edges)
    assert not list(acs.edges)


def test_normalized_saml_assets_scope_ids_and_routes_by_deployment() -> None:
    default_provider, *_ = _scope_assets()
    service_provider, issuer, acs = _scope_assets(
        github_deployment_id="github.example.com",
        github_web_origin="https://github.example.com",
    )

    assert service_provider.as_node.id != default_provider.as_node.id
    assert acs.as_node.properties.acs_url == (
        "https://github.example.com/orgs/acme/saml/consume"
    )
    assert acs.as_node.properties.sp_entity_id == "https://github.example.com/orgs/acme"
    assert issuer.as_node.id == _scope_assets()[1].as_node.id


@pytest.mark.parametrize("issuer", [None, "", "  \t"])
def test_blank_issuer_gives_no_issuer_node_and_no_trust_edge(issuer) -> None:
    """A blank issuer must not stop the rest of the scope's facts or the conversion."""
    service_provider, _, acs = _scope_assets()
    service_provider.issuer = issuer
    blank_issuer = SamlIssuer.model_construct(
        issuer=issuer or "",
        environment_node_id="ORG_1",
        environment_slug="acme",
        environment_type="org",
    )

    assert blank_issuer.as_node is None
    assert {edge.kind for edge in service_provider.edges} == {
        "SAML_Implements",
        "SAML_HasAssertionConsumerService",
    }
    assert service_provider.as_node.kinds == ["SAML_ServiceProvider", "SAML"]
    assert acs.as_node.kinds == ["SAML_AssertionConsumerService", "SAML"]


def test_saml_identity_collection_requests_and_preserves_attributes() -> None:
    assert "attributes {" in ENTERPRISE_SAML_QUERY
    assert "attributes {" in SAML_IDENTITIES_QUERY

    identity = ExternalIdentity(
        guid="guid-1",
        id="external-identity-1",
        environment_slug="acme",
        samlIdentity={
            "username": "alice@example.com",
            "attributes": [
                {
                    "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                    "value": "object-1",
                    "metadata": "source-exact",
                }
            ],
        },
    )

    assert identity.saml_identity is not None
    assert identity.saml_identity.attributes == [
        {
            "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
            "value": "object-1",
            "metadata": "source-exact",
        }
    ]


def test_saml_provider_replays_snake_case_fields_and_deployment_metadata() -> None:
    provider = SamlProvider.model_validate(
        {
            "id": "IDP_1",
            "issuer": "https://issuer.example.com",
            "sso_url": "https://issuer.example.com/sso",
            "signature_method": "rsa-sha256",
            "idp_certificate": "certificate-data",
            "environment_node_id": "ORG_1",
            "environment_name": "Acme",
            "environment_slug": "acme",
            "environment_type": "org",
            "github_deployment_id": "github.example.com",
            "github_web_origin": "https://github.example.com",
        }
    )

    assert provider.sso_url == "https://issuer.example.com/sso"
    assert provider.signature_method == "rsa-sha256"
    assert provider.idp_certificate == "certificate-data"
    assert provider.as_node.kinds == [
        nk.SAML_IDENTITY_PROVIDER, nk.IDENTITY_PROVIDER, "GitHub"
    ]
    assert provider.as_node.properties.github_deployment_id == "github.example.com"
    assert provider.as_node.properties.github_web_origin == "https://github.example.com"


def test_saml_account_edge_emits_contract_evidence_and_direct_user_mapping() -> None:
    identity = _identity_with_lookup()

    edges = list(identity.edges)
    account_edge = next(edge for edge in edges if edge.kind == SAML_HAS_ACCOUNT)
    maps_to_edges = [edge for edge in edges if edge.kind == ek.MAPS_TO_USER]

    assert account_edge.properties.schema_contract_version == "opengraph-saml-v0.3.0"
    assert account_edge.properties.match_values == [
        "Alice@example.com",
        "subject-1",
        "11111111-1111-4111-8111-111111111111",
    ]
    assert account_edge.properties.scoped_exact_match_values == [
        "Alice@example.com",
        "subject-1",
    ]
    assert account_edge.properties.entra_object_id_match_values == ["11111111-1111-4111-8111-111111111111"]
    assert account_edge.properties.direct_binding is True
    assert account_edge.properties.github_direct_binding_source == (
        "GH_ExternalIdentity.saml_identity"
    )
    assert account_edge.properties.github_external_identity_id == "external-identity-1"
    assert account_edge.start.value == _scope_assets()[0].as_node.id
    assert account_edge.end.value == "USER_1"

    assert ek.HAS_EXTERNAL_IDENTITY in {edge.kind for edge in edges}
    assert len(maps_to_edges) == 1
    assert maps_to_edges[0].start.value == "external-identity-1"
    assert maps_to_edges[0].end.value == "USER_1"
    assert maps_to_edges[0].end.match_by == "id"


def test_external_identity_does_not_emit_legacy_foreign_user_correlations() -> None:
    identity = _identity_with_lookup()
    identity._lookup = SimpleNamespace(
        identity_providers_for_environment=lambda _slug: [
            (
                "IDP_1",
                "http://www.okta.com/example",
                "https://example.okta.com/app/github/sso/saml",
                "ORG_1",
                "Acme",
                "org",
                "saml",
            )
        ]
    )

    edges = list(identity.edges)
    maps_to_edges = [edge for edge in edges if edge.kind == ek.MAPS_TO_USER]

    assert "GH_SyncedTo" not in {edge.kind for edge in edges}
    assert len(maps_to_edges) == 1
    assert maps_to_edges[0].end.value == "USER_1"
    assert not getattr(maps_to_edges[0].end, "property_matchers", None)


def test_external_identity_missing_idp_fallback_includes_environment_type() -> None:
    identity = _identity_with_lookup()
    identity._lookup = SimpleNamespace(identity_providers_for_environment=lambda _slug: [])

    assert identity.idp == {
        "id": None,
        "issuer": None,
        "sso_url": None,
        "environment_node_id": None,
        "environment_name": None,
        "environment_type": None,
        "federation_type": None,
    }


def test_org_scim_only_identity_does_not_emit_saml_account_edge() -> None:
    identity = _identity_with_lookup(
        samlIdentity=None,
        scimIdentity={"username": "scim-only@example.com"},
    )

    assert SAML_HAS_ACCOUNT not in {edge.kind for edge in identity.edges}


def test_enterprise_scim_only_identity_emits_managed_user_binding() -> None:
    identity = _identity_with_lookup(
        samlIdentity=None,
        scimIdentity={"username": "managed@example.com"},
    )
    identity._lookup = SimpleNamespace(
        identity_providers_for_environment=lambda _slug: [
            (
                "IDP_1",
                "https://issuer.example.com",
                "https://issuer.example.com/sso",
                "ENT_1",
                "Acme",
                "enterprise",
                "saml",
            )
        ]
    )

    account_edge = _saml_account_edge(identity)

    assert account_edge.properties.match_values == ["managed@example.com"]
    assert account_edge.properties.scoped_exact_match_values == [
        "managed@example.com"
    ]
    assert account_edge.properties.entra_object_id_match_values == []
    assert account_edge.properties.github_direct_binding_source == (
        "GH_ExternalIdentity.scim_identity (Enterprise Managed Users)"
    )


def test_entra_object_id_claim_that_is_not_a_uuid_stays_untyped() -> None:
    identity = _identity_with_lookup(
        samlIdentity={
            "username": "alice@example.com",
            "attributes": [
                {
                    "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                    "value": "not-a-uuid",
                }
            ],
        }
    )

    account_edge = _saml_account_edge(identity)

    assert account_edge.properties.match_values == ["alice@example.com", "not-a-uuid"]
    assert account_edge.properties.entra_object_id_match_values == []
