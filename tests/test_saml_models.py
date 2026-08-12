from types import SimpleNamespace

from openhound_github.kinds import edges as ek
from openhound_github.graphql import ENTERPRISE_SAML_QUERY, SAML_IDENTITIES_QUERY
from openhound_github.models.external_identity import ExternalIdentity
from openhound_github.models.saml_assertion_consumer_service import (
    SamlAssertionConsumerService,
)
from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    SAML_CONTRACT_VERSION,
)
from openhound_github.models.saml_issuer import SamlIssuer
from openhound_github.models.saml_provider import SamlProvider
from openhound_github.models.saml_service_provider import SamlServiceProvider
from openhound_github.saml_entity_panel_queries import (
    ENTITY_PANEL_QUERY_VERSION,
    cypher_string_literal,
    node_entity_panel_queries,
)


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
                    "value": "object-1",
                }
            ],
        },
        "scimIdentity": {"username": "scim-only@example.com"},
        "user": {"id": "USER_1", "login": "alice"},
    }
    data.update(overrides)
    identity = ExternalIdentity.model_validate(data)
    identity._lookup = SimpleNamespace(
        idp_for_environment=lambda _slug: [
            (
                "IDP_1",
                "https://issuer.example.com",
                "https://issuer.example.com/sso",
                "ORG_1",
                "Acme",
                "org",
            )
        ]
    )
    return identity


def _saml_account_edge(identity: ExternalIdentity):
    return next(edge for edge in identity.edges if edge.kind == ek.SAML_HAS_ACCOUNT)


def test_normalized_saml_nodes_expose_contract_metadata() -> None:
    service_provider = SamlServiceProvider(
        id="IDP_1",
        issuer="https://issuer.example.com",
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
    )
    issuer = SamlIssuer(
        issuer="https://issuer.example.com",
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
    )
    acs = SamlAssertionConsumerService(
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
    )

    sp_properties = service_provider.as_node.properties
    issuer_properties = issuer.as_node.properties
    acs_properties = acs.as_node.properties

    assert service_provider.as_node.id == "github:saml:sp:org:acme"
    assert issuer.as_node.id == "github:saml:trusted-issuer:org:acme"
    assert acs.as_node.id == "github:saml:acs:org:acme"
    assert sp_properties.github_deployment_id == DEFAULT_GITHUB_DEPLOYMENT_ID
    assert sp_properties.github_web_origin == DEFAULT_GITHUB_WEB_ORIGIN
    assert sp_properties.schema_contract_version == SAML_CONTRACT_VERSION

    assert issuer_properties.github_deployment_id == DEFAULT_GITHUB_DEPLOYMENT_ID
    assert issuer_properties.github_web_origin == DEFAULT_GITHUB_WEB_ORIGIN
    assert issuer_properties.native_source_field == "GH_SamlIdentityProvider.issuer"
    assert issuer_properties.schema_contract_version == SAML_CONTRACT_VERSION

    assert acs_properties.github_deployment_id == DEFAULT_GITHUB_DEPLOYMENT_ID
    assert acs_properties.github_web_origin == DEFAULT_GITHUB_WEB_ORIGIN
    assert acs_properties.route_source == "github_organization_scope_convention"
    assert acs_properties.schema_contract_version == SAML_CONTRACT_VERSION
    for node in (issuer.as_node, acs.as_node):
        assert node.properties.entity_panel_query_version == (
            ENTITY_PANEL_QUERY_VERSION
        )
        for key, value in node_entity_panel_queries(node.kinds[0], node.id).items():
            assert getattr(node.properties, key) == value
    assert cypher_string_literal("id'\\\n東京") == "'id\\'\\\\\\n東京'"

    implements_edges = list(service_provider.edges)
    assert len(implements_edges) == 1
    assert implements_edges[0].start.value == "IDP_1"
    assert implements_edges[0].end.value == "github:saml:sp:org:acme"
    assert (
        implements_edges[0].properties.schema_contract_version
        == SAML_CONTRACT_VERSION
    )
    assert (
        next(iter(issuer.edges)).properties.schema_contract_version
        == SAML_CONTRACT_VERSION
    )
    assert (
        next(iter(acs.edges)).properties.schema_contract_version
        == SAML_CONTRACT_VERSION
    )


def test_normalized_saml_nodes_scope_ids_and_routes_by_deployment() -> None:
    service_provider = SamlServiceProvider(
        id="IDP_1",
        issuer="https://issuer.example.com",
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
        github_deployment_id="github.example.com",
        github_web_origin="https://github.example.com",
    )
    issuer = SamlIssuer(
        issuer="https://issuer.example.com",
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
        github_deployment_id="github.example.com",
        github_web_origin="https://github.example.com",
    )
    acs = SamlAssertionConsumerService(
        environment_node_id="ORG_1",
        environment_name="Acme",
        environment_slug="acme",
        environment_type="org",
        github_deployment_id="github.example.com",
        github_web_origin="https://github.example.com",
    )

    assert service_provider.as_node.id == "github:github.example.com:saml:sp:org:acme"
    assert issuer.as_node.id == "github:github.example.com:saml:trusted-issuer:org:acme"
    assert acs.as_node.id == "github:github.example.com:saml:acs:org:acme"
    assert acs.as_node.properties.acs_url == (
        "https://github.example.com/orgs/acme/saml/consume"
    )
    assert service_provider.as_node.properties.entity_id == (
        "https://github.example.com/orgs/acme"
    )


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
    assert provider.as_node.properties.github_deployment_id == "github.example.com"
    assert provider.as_node.properties.github_web_origin == "https://github.example.com"


def test_saml_account_edge_emits_contract_evidence_without_changing_legacy_edges() -> None:
    identity = _identity_with_lookup()

    edges = list(identity.edges)
    account_edge = next(edge for edge in edges if edge.kind == ek.SAML_HAS_ACCOUNT)

    assert account_edge.properties.schema_contract_version == SAML_CONTRACT_VERSION
    assert account_edge.properties.match_values == [
        "Alice@example.com",
        "subject-1",
        "object-1",
    ]
    assert account_edge.properties.scoped_exact_match_values == [
        "Alice@example.com",
        "subject-1",
    ]
    assert account_edge.properties.entra_object_id_match_values == ["object-1"]
    assert account_edge.properties.direct_binding is True
    assert account_edge.properties.direct_binding_source == (
        "GH_ExternalIdentity.saml_identity"
    )
    assert account_edge.properties.external_identity_id == "external-identity-1"
    assert account_edge.start.value == "github:saml:sp:org:acme"

    assert ek.HAS_EXTERNAL_IDENTITY in {edge.kind for edge in edges}
    assert ek.MAPS_TO_USER in {edge.kind for edge in edges}


def test_org_scim_only_identity_does_not_emit_saml_account_edge() -> None:
    identity = _identity_with_lookup(
        samlIdentity=None,
        scimIdentity={"username": "scim-only@example.com"},
    )

    assert ek.SAML_HAS_ACCOUNT not in {edge.kind for edge in identity.edges}


def test_enterprise_scim_only_identity_emits_managed_user_binding() -> None:
    identity = _identity_with_lookup(
        samlIdentity=None,
        scimIdentity={"username": "managed@example.com"},
    )
    identity._lookup = SimpleNamespace(
        idp_for_environment=lambda _slug: [
            (
                "IDP_1",
                "https://issuer.example.com",
                "https://issuer.example.com/sso",
                "ENT_1",
                "Acme",
                "enterprise",
            )
        ]
    )

    account_edge = _saml_account_edge(identity)

    assert account_edge.properties.match_values == ["managed@example.com"]
    assert account_edge.properties.scoped_exact_match_values == [
        "managed@example.com"
    ]
    assert account_edge.properties.entra_object_id_match_values == []
    assert account_edge.properties.direct_binding_source == (
        "GH_ExternalIdentity.scim_identity (Enterprise Managed Users)"
    )
