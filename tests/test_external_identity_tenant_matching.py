from dataclasses import asdict

import pytest

from openhound_github.kinds import edges as ek
from openhound_github.models.enterprise_external_identity import (
    EnterpriseExternalIdentity,
)
from openhound_github.models.external_identity import ExternalIdentity


class _OrgLookup:
    def __init__(self, tenant_domain: str):
        self.tenant_domain = tenant_domain

    def org_id_for_login(self, login: str) -> str:
        return f"org:{login}"

    def idp_for_org(self, login: str) -> list[tuple[str, str, str | None]]:
        return [
            (
                f"idp:{login}",
                "http://www.okta.com/example",
                f"https://{self.tenant_domain}/app/github/sso/saml",
            )
        ]


class _ProviderOrgLookup:
    def __init__(self, issuer: str, sso_url: str | None):
        self.issuer = issuer
        self.sso_url = sso_url

    def org_id_for_login(self, login: str) -> str:
        return f"org:{login}"

    def idp_for_org(self, login: str) -> list[tuple[str, str, str | None]]:
        return [(f"idp:{login}", self.issuer, self.sso_url)]


def _org_external_identity(org_login: str, tenant_domain: str) -> ExternalIdentity:
    identity = ExternalIdentity.model_validate(
        {
            "guid": f"guid:{org_login}",
            "id": f"external-identity:{org_login}",
            "samlIdentity": {"username": "duplicate@example.com"},
            "scimIdentity": None,
            "user": {"id": f"github-user:{org_login}", "login": "duplicate"},
            "org_login": org_login,
        }
    )
    identity._lookup = _OrgLookup(tenant_domain)
    return identity


def _foreign_user_edges(identity):
    edges = list(identity.edges)
    maps_to = next(
        edge
        for edge in edges
        if edge.kind == ek.MAPS_TO_USER and getattr(edge.end, "property_matchers", None)
    )
    synced_to = next(edge for edge in edges if edge.kind == ek.SYNCED_TO_GH_USER)
    return maps_to, synced_to


def test_org_external_identity_scopes_duplicate_okta_username_by_tenant() -> None:
    first = _foreign_user_edges(
        _org_external_identity("first-org", "first.example.okta.com")
    )
    second = _foreign_user_edges(
        _org_external_identity("second-org", "second.example.okta.com")
    )

    for edges, tenant_domain in (
        (first, "first.example.okta.com"),
        (second, "second.example.okta.com"),
    ):
        for endpoint in (edges[0].end, edges[1].start):
            assert endpoint.kind == "Okta_User"
            assert {
                matcher.key: matcher.value for matcher in endpoint.property_matchers
            } == {
                "tenant_domain": tenant_domain,
                "name": "DUPLICATE@EXAMPLE.COM",
            }

    emitted_endpoint = asdict(first[0].end)
    assert emitted_endpoint["kind"] == "Okta_User"
    assert emitted_endpoint["match_by"] == "property"
    assert [
        {"key": matcher["key"], "value": matcher["value"]}
        for matcher in emitted_endpoint["property_matchers"]
    ] == [
        {"key": "tenant_domain", "value": "first.example.okta.com"},
        {"key": "name", "value": "DUPLICATE@EXAMPLE.COM"},
    ]

    maps_to, synced_to = first
    assert maps_to.start.value == "external-identity:first-org"
    assert maps_to.properties.traversable is False
    assert synced_to.end.value == "external-identity:first-org"
    assert synced_to.properties.traversable is True
    assert synced_to.properties.composed is True
    assert synced_to.properties.query_composition is not None
    assert "GH_SyncedToEnvironment" in synced_to.properties.query_composition


def _enterprise_external_identity(tenant_domain: str) -> EnterpriseExternalIdentity:
    return EnterpriseExternalIdentity.model_validate(
        {
            "guid": f"guid:{tenant_domain}",
            "id": f"external-identity:{tenant_domain}",
            "samlIdentity": {"username": "duplicate@example.com"},
            "scimIdentity": None,
            "user": {"id": f"github-user:{tenant_domain}", "login": "duplicate"},
            "saml_provider_id": f"idp:{tenant_domain}",
            "saml_provider_issuer": "http://www.okta.com/example",
            "saml_provider_sso_url": (f"https://{tenant_domain}/app/github/sso/saml"),
            "enterprise_node_id": "enterprise-id",
            "enterprise_slug": "example-enterprise",
        }
    )


def test_enterprise_external_identity_scopes_duplicate_okta_username_by_tenant() -> (
    None
):
    first = _foreign_user_edges(_enterprise_external_identity("first.example.okta.com"))
    second = _foreign_user_edges(
        _enterprise_external_identity("second.example.okta.com")
    )

    for edges, tenant_domain in (
        (first, "first.example.okta.com"),
        (second, "second.example.okta.com"),
    ):
        for endpoint in (edges[0].end, edges[1].start):
            assert endpoint.kind == "Okta_User"
            assert {
                matcher.key: matcher.value for matcher in endpoint.property_matchers
            } == {
                "tenant_domain": tenant_domain,
                "name": "DUPLICATE@EXAMPLE.COM",
            }

    emitted_endpoint = asdict(first[0].end)
    assert emitted_endpoint["kind"] == "Okta_User"
    assert emitted_endpoint["match_by"] == "property"
    assert [
        {"key": matcher["key"], "value": matcher["value"]}
        for matcher in emitted_endpoint["property_matchers"]
    ] == [
        {"key": "tenant_domain", "value": "first.example.okta.com"},
        {"key": "name", "value": "DUPLICATE@EXAMPLE.COM"},
    ]

    maps_to, synced_to = first
    assert maps_to.start.value == "external-identity:first.example.okta.com"
    assert maps_to.properties.traversable is False
    assert synced_to.end.value == "github-user:first.example.okta.com"
    assert synced_to.properties.traversable is True
    assert synced_to.properties.composed is False


@pytest.mark.parametrize(
    ("issuer", "sso_url", "expected_kind", "scope_key", "scope_value"),
    [
        (
            "https://auth.pingone.com/ping-environment-id/saml20/idp/sso",
            None,
            "PingOne_User",
            "environmentid",
            "ping-environment-id",
        ),
    ],
)
def test_enterprise_external_identity_uses_provider_environment_scope(
    issuer: str,
    sso_url: str | None,
    expected_kind: str,
    scope_key: str,
    scope_value: str,
) -> None:
    identity = EnterpriseExternalIdentity.model_validate(
        {
            "guid": "provider-guid",
            "id": "provider-external-identity",
            "samlIdentity": {"username": "user@example.com"},
            "scimIdentity": None,
            "user": {"id": "github-user", "login": "user"},
            "saml_provider_id": "provider-id",
            "saml_provider_issuer": issuer,
            "saml_provider_sso_url": sso_url,
            "enterprise_node_id": "enterprise-id",
            "enterprise_slug": "example-enterprise",
        }
    )

    maps_to, synced_to = _foreign_user_edges(identity)
    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == expected_kind
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            scope_key: scope_value,
            "name": "USER@EXAMPLE.COM",
        }


def _enterprise_entra_external_identity(
    tenant_claim: str | None = "11111111-2222-3333-4444-555555555555",
    object_id_claim: str | None = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
) -> EnterpriseExternalIdentity:
    attributes = []
    if tenant_claim is not None:
        attributes.append(
            {
                "name": "http://schemas.microsoft.com/identity/claims/tenantid",
                "value": tenant_claim,
            }
        )
    if object_id_claim is not None:
        attributes.append(
            {
                "name": (
                    "http://schemas.microsoft.com/identity/claims/objectidentifier"
                ),
                "value": object_id_claim,
            }
        )
    return EnterpriseExternalIdentity.model_validate(
        {
            "guid": "entra-guid",
            "id": "entra-external-identity",
            "samlIdentity": {
                "username": "opaque-pairwise-name-id",
                "attributes": attributes,
            },
            "scimIdentity": None,
            "user": {"id": "github-user", "login": "user"},
            "saml_provider_id": "provider-id",
            "saml_provider_issuer": (
                "https://sts.windows.net/11111111-2222-3333-4444-555555555555/"
            ),
            "saml_provider_sso_url": (
                "https://login.microsoftonline.com/"
                "11111111-2222-3333-4444-555555555555/saml2"
            ),
            "enterprise_node_id": "enterprise-id",
            "enterprise_slug": "example-enterprise",
        }
    )


def test_enterprise_entra_external_identity_uses_explicit_saml_claims() -> None:
    identity = _enterprise_entra_external_identity()

    maps_to, synced_to = _foreign_user_edges(identity)
    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == "AZUser"
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            "tenantid": "11111111-2222-3333-4444-555555555555".upper(),
            "objectid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        }

    emitted_endpoint = asdict(maps_to.end)
    assert emitted_endpoint["kind"] == "AZUser"
    assert emitted_endpoint["match_by"] == "property"
    assert [
        {"key": matcher["key"], "value": matcher["value"]}
        for matcher in emitted_endpoint["property_matchers"]
    ] == [
        {
            "key": "tenantid",
            "value": "11111111-2222-3333-4444-555555555555".upper(),
        },
        {
            "key": "objectid",
            "value": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        },
    ]


@pytest.mark.parametrize(
    ("tenant_claim", "object_id_claim"),
    [
        (None, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        ("11111111-2222-3333-4444-555555555555", None),
        (
            "99999999-8888-7777-6666-555555555555",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ),
    ],
)
def test_enterprise_entra_external_identity_omits_edges_without_consistent_claims(
    tenant_claim: str | None,
    object_id_claim: str | None,
) -> None:
    edges = list(
        _enterprise_entra_external_identity(tenant_claim, object_id_claim).edges
    )

    assert ek.SYNCED_TO_GH_USER not in {edge.kind for edge in edges}
    assert not any(
        edge.kind == ek.MAPS_TO_USER and getattr(edge.end, "property_matchers", None)
        for edge in edges
    )


def _org_entra_external_identity(
    tenant_claim: str | None = "11111111-2222-3333-4444-555555555555",
    object_id_claim: str | None = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
) -> ExternalIdentity:
    attributes = []
    if tenant_claim is not None:
        attributes.append(
            {
                "name": "http://schemas.microsoft.com/identity/claims/tenantid",
                "value": tenant_claim,
            }
        )
    if object_id_claim is not None:
        attributes.append(
            {
                "name": (
                    "http://schemas.microsoft.com/identity/claims/objectidentifier"
                ),
                "value": object_id_claim,
            }
        )
    identity = ExternalIdentity.model_validate(
        {
            "guid": "org-entra-guid",
            "id": "org-entra-external-identity",
            "samlIdentity": {
                "username": "opaque-pairwise-name-id",
                "attributes": attributes,
            },
            "scimIdentity": None,
            "user": {"id": "github-user", "login": "user"},
            "org_login": "entra-org",
        }
    )
    identity._lookup = _ProviderOrgLookup(
        "https://sts.windows.net/11111111-2222-3333-4444-555555555555/",
        (
            "https://login.microsoftonline.com/"
            "11111111-2222-3333-4444-555555555555/saml2"
        ),
    )
    return identity


def test_org_entra_external_identity_uses_explicit_saml_claims() -> None:
    maps_to, synced_to = _foreign_user_edges(_org_entra_external_identity())

    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == "AZUser"
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            "tenantid": "11111111-2222-3333-4444-555555555555".upper(),
            "objectid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        }

    emitted_endpoint = asdict(maps_to.end)
    assert emitted_endpoint["kind"] == "AZUser"
    assert emitted_endpoint["match_by"] == "property"
    assert [matcher["key"] for matcher in emitted_endpoint["property_matchers"]] == [
        "tenantid",
        "objectid",
    ]


@pytest.mark.parametrize(
    ("tenant_claim", "object_id_claim"),
    [
        (None, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        ("11111111-2222-3333-4444-555555555555", None),
        (
            "99999999-8888-7777-6666-555555555555",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ),
    ],
)
def test_org_entra_external_identity_omits_edges_without_consistent_claims(
    tenant_claim: str | None,
    object_id_claim: str | None,
) -> None:
    edges = list(_org_entra_external_identity(tenant_claim, object_id_claim).edges)

    assert ek.SYNCED_TO_GH_USER not in {edge.kind for edge in edges}
    assert not any(
        edge.kind == ek.MAPS_TO_USER and getattr(edge.end, "property_matchers", None)
        for edge in edges
    )


def test_org_pingone_external_identity_keeps_environment_and_name_edges() -> None:
    identity = ExternalIdentity.model_validate(
        {
            "guid": "org-pingone-guid",
            "id": "org-pingone-external-identity",
            "samlIdentity": {"username": "opaque-pingone-subject"},
            "scimIdentity": None,
            "user": {"id": "github-user", "login": "user"},
            "org_login": "pingone-org",
        }
    )
    identity._lookup = _ProviderOrgLookup(
        "https://auth.pingone.com/ping-environment-id/saml20/idp/sso",
        None,
    )

    maps_to, synced_to = _foreign_user_edges(identity)
    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == "PingOne_User"
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            "environmentid": "ping-environment-id",
            "name": "OPAQUE-PINGONE-SUBJECT",
        }


class _UnscopedOktaOrgLookup(_OrgLookup):
    def idp_for_org(self, login: str) -> list[tuple[str, str, str | None]]:
        return [(f"idp:{login}", "http://www.okta.com/example", None)]


def test_external_identities_omit_foreign_user_edges_without_tenant_scope() -> None:
    org_identity = _org_external_identity("unscoped-org", "unused.okta.com")
    org_identity._lookup = _UnscopedOktaOrgLookup("unused.okta.com")

    enterprise_identity = EnterpriseExternalIdentity.model_validate(
        {
            "guid": "unscoped-enterprise-guid",
            "id": "unscoped-enterprise-external-identity",
            "samlIdentity": {"username": "user@example.com"},
            "scimIdentity": None,
            "user": {"id": "github-user", "login": "user"},
            "saml_provider_id": "provider-id",
            "saml_provider_issuer": "http://www.okta.com/example",
            "saml_provider_sso_url": None,
            "enterprise_node_id": "enterprise-id",
            "enterprise_slug": "example-enterprise",
        }
    )

    for identity in (org_identity, enterprise_identity):
        edges = list(identity.edges)
        assert ek.SYNCED_TO_GH_USER not in {edge.kind for edge in edges}
        assert not any(
            edge.kind == ek.MAPS_TO_USER
            and getattr(edge.end, "property_matchers", None)
            for edge in edges
        )
