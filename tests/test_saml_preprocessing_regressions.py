import duckdb

from openhound_github.kinds import edges as ek
from openhound_github.models.enterprise_external_identity import (
    EnterpriseExternalIdentity,
)
from openhound_github.models.external_identity import ExternalIdentity
from openhound_github.models.saml_provider import SamlProvider
from openhound_github.models.saml import (
    SAML_CONTRACT_VERSION,
    GithubSamlAssertionConsumerService,
    GithubSamlIssuer,
    GithubSamlServiceProvider,
    github_deployment_context,
    github_enterprise_acs_url,
    github_enterprise_saml_service_provider_id,
    github_org_acs_url,
    github_org_saml_service_provider_id,
    org_saml_acs_row,
    org_saml_issuer_row,
    org_saml_service_provider_row,
)
from openhound_github.transforms import transforms


ORG_SAML_PROVIDER_ROW = {
    "id": "MDQ6U2FtbElkZW50aXR5UHJvdmlkZXIx",
    "issuer": "https://sts.windows.net/example/",
    "org_login": "kng-emea",
    "org_name": "KNG EMEA",
    "org_node_id": "O_kgDOExample",
}


class _OrgLookup:
    def org_id_for_login(self, login: str) -> str:
        assert login == "kng-emea"
        return "O_kgDOExample"

    def idp_for_org(self, login: str) -> list[tuple[str, str, str]]:
        assert login == "kng-emea"
        return [
            (
                "MDQ6U2FtbElkZW50aXR5UHJvdmlkZXIx",
                "https://sts.windows.net/example/",
                "https://login.microsoftonline.com/example/saml2",
            )
        ]


def _saml_account_edge(asset):
    return next(edge for edge in asset.edges if edge.kind == ek.SAML_HAS_ACCOUNT)


def _saml_implements_edge(asset):
    return next(edge for edge in asset.edges if edge.kind == ek.SAML_IMPLEMENTS)


def test_org_saml_provider_replays_dlt_snake_case_fields() -> None:
    provider = SamlProvider.model_validate(
        {
            **ORG_SAML_PROVIDER_ROW,
            "sso_url": "https://login.microsoftonline.com/example/saml2",
            "signature_method": "rsa-sha256",
            "idp_certificate": "certificate-data",
        }
    )

    assert provider.sso_url == "https://login.microsoftonline.com/example/saml2"
    assert provider.signature_method == "rsa-sha256"
    assert provider.idp_certificate == "certificate-data"


def test_org_saml_row_builders_accept_dlt_mapping_rows() -> None:
    service_provider = org_saml_service_provider_row(ORG_SAML_PROVIDER_ROW)
    issuer = org_saml_issuer_row(ORG_SAML_PROVIDER_ROW)
    acs = org_saml_acs_row(ORG_SAML_PROVIDER_ROW)

    assert service_provider == {
        "id": "github:saml:sp:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "saml_provider_id": "MDQ6U2FtbElkZW50aXR5UHJvdmlkZXIx",
        "issuer_id": "github:saml:trusted-issuer:org:kng-emea",
        "acs_id": "github:saml:acs:org:kng-emea",
        "github_deployment_id": "github.com",
        "github_web_origin": "https://github.com",
        "enabled": True,
    }
    assert issuer == {
        "id": "github:saml:trusted-issuer:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "github_deployment_id": "github.com",
        "github_web_origin": "https://github.com",
        "entity_id": "https://sts.windows.net/example/",
    }
    assert acs == {
        "id": "github:saml:acs:org:kng-emea",
        "native_id": "O_kgDOExample",
        "scope_type": "organization",
        "scope_slug": "kng-emea",
        "github_deployment_id": "github.com",
        "github_web_origin": "https://github.com",
        "acs_url": "https://github.com/orgs/kng-emea/saml/consume",
        "sp_entity_id": "https://github.com/orgs/kng-emea",
    }


def test_normalized_saml_ids_and_routes_are_scoped_by_github_deployment() -> None:
    assert github_deployment_context("https://api.github.com") == (
        "github.com",
        "https://github.com",
    )
    assert github_org_saml_service_provider_id("example-org") == (
        "github:saml:sp:org:example-org"
    )

    first_deployment = github_deployment_context(
        "https://ghe-a.example.test/api/v3"
    )
    second_deployment = github_deployment_context(
        "https://ghe-b.example.test/api/v3"
    )

    assert github_org_saml_service_provider_id(
        "example-org", first_deployment[0]
    ) == "github:ghe-a.example.test:saml:sp:org:example-org"
    assert github_org_saml_service_provider_id(
        "example-org", first_deployment[0]
    ) != github_org_saml_service_provider_id(
        "example-org", second_deployment[0]
    )
    assert github_enterprise_saml_service_provider_id(
        "example-enterprise", first_deployment[0]
    ) == "github:ghe-a.example.test:saml:sp:enterprise:example-enterprise"
    assert github_org_acs_url("example-org", first_deployment[1]) == (
        "https://ghe-a.example.test/orgs/example-org/saml/consume"
    )
    assert github_enterprise_acs_url(
        "example-enterprise", first_deployment[1]
    ) == (
        "https://ghe-a.example.test/enterprises/example-enterprise/saml/consume"
    )

    provider = {
        **ORG_SAML_PROVIDER_ROW,
        "github_deployment_id": first_deployment[0],
        "github_web_origin": first_deployment[1],
    }
    service_provider = org_saml_service_provider_row(provider)
    acs = org_saml_acs_row(provider)

    assert service_provider is not None
    assert acs is not None
    assert service_provider["id"] == (
        "github:ghe-a.example.test:saml:sp:org:kng-emea"
    )
    assert service_provider["issuer_id"].startswith(
        "github:ghe-a.example.test:saml:"
    )
    assert service_provider["acs_id"].startswith(
        "github:ghe-a.example.test:saml:"
    )
    assert acs["acs_url"] == (
        "https://ghe-a.example.test/orgs/kng-emea/saml/consume"
    )

    identity = ExternalIdentity.model_validate(
        {
            "guid": "external-guid",
            "id": "external-identity-id",
            "samlIdentity": {"username": "alice@example.test"},
            "scimIdentity": None,
            "user": {"id": "github-user-id", "login": "alice"},
            "org_login": "kng-emea",
            "github_deployment_id": first_deployment[0],
        }
    )
    identity._lookup = _OrgLookup()
    account = _saml_account_edge(identity)

    assert account.start.value == service_provider["id"]
    assert account.start.match_by == "id"
    assert account.end.value == "github-user-id"
    assert account.end.match_by == "id"


def test_normalized_github_topology_is_fact_local_v0_3() -> None:
    service_provider_row = org_saml_service_provider_row(ORG_SAML_PROVIDER_ROW)
    issuer_row = org_saml_issuer_row(ORG_SAML_PROVIDER_ROW)
    acs_row = org_saml_acs_row(ORG_SAML_PROVIDER_ROW)
    assert service_provider_row is not None
    assert issuer_row is not None
    assert acs_row is not None

    service_provider = GithubSamlServiceProvider.model_validate(service_provider_row)
    issuer = GithubSamlIssuer.model_validate(issuer_row)
    acs = GithubSamlAssertionConsumerService.model_validate(acs_row)

    assert service_provider.as_node.properties.schema_contract_version == (
        SAML_CONTRACT_VERSION
    )
    assert issuer.as_node.properties.schema_contract_version == SAML_CONTRACT_VERSION
    assert acs.as_node.properties.schema_contract_version == SAML_CONTRACT_VERSION
    assert issuer.as_node.properties.entity_id == ORG_SAML_PROVIDER_ROW["issuer"]
    assert issuer.as_node.properties.native_source_field == (
        "GH_SamlIdentityProvider.issuer"
    )
    assert acs.as_node.properties.route_source == (
        "github_organization_scope_convention"
    )
    assert all(
        edge.properties.schema_contract_version == SAML_CONTRACT_VERSION
        for edge in service_provider.edges
    )

    implements = _saml_implements_edge(service_provider)
    assert implements.start.value == ORG_SAML_PROVIDER_ROW["id"]
    assert implements.start.match_by == "id"
    assert implements.end.value == service_provider_row["id"]
    assert implements.end.match_by == "id"


def test_enterprise_saml_implements_uses_native_provider_node() -> None:
    service_provider = GithubSamlServiceProvider.model_validate(
        {
            "id": "github:saml:sp:enterprise:kng-global",
            "native_id": "E_kgDOExample",
            "scope_type": "enterprise",
            "scope_slug": "kng-global",
            "saml_provider_id": "enterprise-saml-provider-id",
            "issuer_id": "github:saml:trusted-issuer:enterprise:kng-global",
            "acs_id": "github:saml:acs:enterprise:kng-global",
            "enabled": True,
        }
    )

    implements = _saml_implements_edge(service_provider)
    assert implements.start.value == "enterprise-saml-provider-id"
    assert implements.start.match_by == "id"
    assert implements.end.value == service_provider.id
    assert implements.end.match_by == "id"


def test_org_external_identity_emits_saml_only_direct_binding() -> None:
    identity = ExternalIdentity.model_validate(
        {
            "guid": "external-guid",
            "id": "external-identity-id",
            "samlIdentity": {
                "nameId": "Alice@Example.com",
                "username": "Alice@Example.com",
                "attributes": [
                    {
                        "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                        "value": "11111111-2222-3333-4444-555555555555",
                    }
                ],
            },
            "scimIdentity": {"username": "scim-lookup-only@example.com"},
            "user": {"id": "github-user-id", "login": "alice"},
            "org_login": "kng-emea",
        }
    )
    identity._lookup = _OrgLookup()

    account = _saml_account_edge(identity)

    assert account.start.value == "github:saml:sp:org:kng-emea"
    assert account.end.value == "github-user-id"
    assert account.properties.schema_contract_version == SAML_CONTRACT_VERSION
    assert account.properties.match_values == [
        "Alice@Example.com",
        "11111111-2222-3333-4444-555555555555",
    ]
    assert account.properties.scoped_exact_match_values == ["Alice@Example.com"]
    assert account.properties.entra_object_id_match_values == [
        "11111111-2222-3333-4444-555555555555"
    ]
    assert account.properties.direct_binding is True
    assert account.properties.direct_binding_source == (
        "GH_ExternalIdentity.saml_identity"
    )
    assert account.properties.external_identity_id == "external-identity-id"
    assert "scim-lookup-only@example.com" not in account.properties.match_values


def test_org_scim_only_external_identity_emits_no_saml_account() -> None:
    identity = ExternalIdentity.model_validate(
        {
            "guid": "external-guid",
            "id": "external-identity-id",
            "samlIdentity": {},
            "scimIdentity": {"username": "scim-only@example.com"},
            "user": {"id": "github-user-id", "login": "alice"},
            "org_login": "kng-emea",
        }
    )
    identity._lookup = _OrgLookup()

    assert ek.SAML_HAS_ACCOUNT not in {edge.kind for edge in identity.edges}


def test_enterprise_external_identity_emits_saml_only_direct_binding() -> None:
    identity = EnterpriseExternalIdentity.model_validate(
        {
            "guid": "enterprise-external-guid",
            "id": "enterprise-external-identity-id",
            "samlIdentity": {
                "nameId": "subject-123",
                "username": "Alice@Example.com",
                "attributes": [
                    {
                        "name": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                        "value": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    }
                ],
            },
            "scimIdentity": {"username": "scim-lookup-only@example.com"},
            "user": {"id": "github-enterprise-user-id", "login": "alice_emu"},
            "saml_provider_id": "enterprise-saml-provider-id",
            "saml_provider_issuer": "https://sts.windows.net/example/",
            "saml_provider_sso_url": "https://login.microsoftonline.com/example/saml2",
            "enterprise_node_id": "E_kgDOExample",
            "enterprise_slug": "kng-global",
        }
    )

    account = _saml_account_edge(identity)

    assert account.start.value == "github:saml:sp:enterprise:kng-global"
    assert account.end.value == "github-enterprise-user-id"
    assert account.properties.match_values == [
        "Alice@Example.com",
        "subject-123",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    ]
    assert account.properties.scoped_exact_match_values == [
        "Alice@Example.com",
        "subject-123",
    ]
    assert account.properties.entra_object_id_match_values == [
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    ]
    assert account.properties.direct_binding is True
    assert account.properties.external_identity_id == (
        "enterprise-external-identity-id"
    )
    assert "scim-lookup-only@example.com" not in account.properties.match_values


def test_enterprise_managed_user_scim_identity_is_a_direct_saml_binding() -> None:
    identity = EnterpriseExternalIdentity.model_validate(
        {
            "guid": "enterprise-external-guid",
            "id": "enterprise-external-identity-id",
            "samlIdentity": None,
            "scimIdentity": {"username": "Alice@Example.com"},
            "user": {"id": "github-enterprise-user-id", "login": "alice_emu"},
            "saml_provider_id": "enterprise-saml-provider-id",
            "saml_provider_issuer": "https://preview.example.okta.com",
            "saml_provider_sso_url": "https://preview.example.okta.com/sso/saml",
            "enterprise_node_id": "E_kgDOExample",
            "enterprise_slug": "kng-global",
        }
    )

    account = _saml_account_edge(identity)

    assert account.properties.match_values == ["Alice@Example.com"]
    assert account.properties.scoped_exact_match_values == ["Alice@Example.com"]
    assert account.properties.entra_object_id_match_values == []
    assert account.properties.direct_binding is True
    assert account.properties.direct_binding_source == (
        "GH_ExternalIdentity.scim_identity (Enterprise Managed Users)"
    )


def test_transforms_create_zero_row_optional_branch_inputs() -> None:
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA github")
    con.execute(
        "CREATE TABLE github.branches (id VARCHAR, repository_node_id VARCHAR)"
    )
    con.execute(
        "CREATE TABLE github.repo_roles (id BIGINT, repository_node_id VARCHAR)"
    )

    transforms(con)

    for table in (
        "branches",
        "branch_protection_rules",
        "repo_roles",
        "branch_bpr",
        "actor_branch_bypass",
        "unprotected_branches",
        "actor_branch_gates",
        "role_can_create_branch",
    ):
        assert con.execute(f"SELECT COUNT(*) FROM github.{table}").fetchone() == (0,)
