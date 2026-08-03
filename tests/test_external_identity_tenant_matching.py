from dataclasses import asdict

import pytest

from openhound_github.kinds import edges as ek
from openhound_github.models.external_identity import ExternalIdentity


class _Lookup:
    def __init__(
        self,
        issuer: str,
        sso_url: str | None,
        environment_type: str = "org",
    ):
        self.issuer = issuer
        self.sso_url = sso_url
        self.environment_type = environment_type

    def idp_for_environment(self, slug: str):
        return [
            (
                f"idp:{slug}",
                self.issuer,
                self.sso_url,
                f"environment:{slug}",
                slug,
                self.environment_type,
            )
        ]


class _MissingIdpLookup:
    def idp_for_environment(self, slug: str):
        return []


def _identity(
    slug: str,
    issuer: str,
    sso_url: str | None,
    saml_identity: dict,
    environment_type: str = "org",
) -> ExternalIdentity:
    identity = ExternalIdentity.model_validate(
        {
            "guid": f"guid:{slug}",
            "id": f"external-identity:{slug}",
            "samlIdentity": saml_identity,
            "scimIdentity": None,
            "user": {"id": f"github-user:{slug}", "login": "duplicate"},
            "environment_slug": slug,
        }
    )
    identity._lookup = _Lookup(issuer, sso_url, environment_type)
    return identity


def _foreign_user_edges(identity: ExternalIdentity):
    edges = list(identity.edges)
    maps_to = next(
        edge
        for edge in edges
        if edge.kind == ek.MAPS_TO_USER
        and getattr(edge.end, "property_matchers", None)
    )
    synced_to = next(edge for edge in edges if edge.kind == ek.SYNCED_TO_GH_USER)
    return maps_to, synced_to


def test_external_identity_scopes_duplicate_okta_username_by_tenant() -> None:
    first = _foreign_user_edges(
        _identity(
            "first-org",
            "http://www.okta.com/example",
            "https://first.example.okta.com/app/github/sso/saml",
            {"username": "duplicate@example.com"},
        )
    )
    second = _foreign_user_edges(
        _identity(
            "second-org",
            "http://www.okta.com/example",
            "https://second.example.okta.com/app/github/sso/saml",
            {"username": "duplicate@example.com"},
            environment_type="enterprise",
        )
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


def test_external_identity_uses_pingone_environment_scope() -> None:
    maps_to, synced_to = _foreign_user_edges(
        _identity(
            "pingone-org",
            "https://auth.pingone.com/ping-environment-id/saml20/idp/sso",
            None,
            {"username": "opaque-pingone-subject"},
        )
    )

    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == "PingOne_User"
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            "environmentid": "ping-environment-id",
            "name": "OPAQUE-PINGONE-SUBJECT",
        }


def _entra_identity(
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
    return _identity(
        "entra-org",
        "https://sts.windows.net/11111111-2222-3333-4444-555555555555/",
        (
            "https://login.microsoftonline.com/"
            "11111111-2222-3333-4444-555555555555/saml2"
        ),
        {
            "username": "opaque-pairwise-name-id",
            "attributes": attributes,
        },
    )


def test_entra_external_identity_uses_explicit_saml_claims() -> None:
    maps_to, synced_to = _foreign_user_edges(_entra_identity())

    for endpoint in (maps_to.end, synced_to.start):
        assert endpoint.kind == "AZUser"
        assert {
            matcher.key: matcher.value for matcher in endpoint.property_matchers
        } == {
            "tenantid": "11111111-2222-3333-4444-555555555555".upper(),
            "objectid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        }


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
def test_entra_external_identity_omits_unsafe_foreign_user_edges(
    tenant_claim: str | None,
    object_id_claim: str | None,
) -> None:
    edges = list(_entra_identity(tenant_claim, object_id_claim).edges)

    assert ek.SYNCED_TO_GH_USER not in {edge.kind for edge in edges}
    assert not any(
        edge.kind == ek.MAPS_TO_USER
        and getattr(edge.end, "property_matchers", None)
        for edge in edges
    )


def test_external_identity_omits_okta_edges_without_tenant_scope() -> None:
    edges = list(
        _identity(
            "unscoped-org",
            "http://www.okta.com/example",
            None,
            {"username": "user@example.com"},
        ).edges
    )

    assert ek.SYNCED_TO_GH_USER not in {edge.kind for edge in edges}
    assert not any(
        edge.kind == ek.MAPS_TO_USER
        and getattr(edge.end, "property_matchers", None)
        for edge in edges
    )


def test_external_identity_missing_idp_fallback_includes_environment_type() -> None:
    identity = _identity(
        "missing-idp",
        "http://www.okta.com/example",
        "https://example.okta.com/app/github/sso/saml",
        {"username": "user@example.com"},
    )
    identity._lookup = _MissingIdpLookup()

    assert identity.idp == {
        "id": None,
        "issuer": None,
        "sso_url": None,
        "environment_node_id": None,
        "environment_name": None,
        "environment_type": None,
    }
