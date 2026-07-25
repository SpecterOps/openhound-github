from types import SimpleNamespace

import pytest

from openhound_github.models.saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    ENTRA_OBJECT_ID_CLAIM,
    github_deployment_context,
    github_enterprise_acs_url,
    github_enterprise_saml_service_provider_id,
    github_org_acs_url,
    github_org_saml_service_provider_id,
    saml_account_match_values,
    saml_attribute_match_values,
)


def test_github_dot_com_deployment_preserves_default_contract_scope() -> None:
    assert github_deployment_context("https://api.github.com") == (
        DEFAULT_GITHUB_DEPLOYMENT_ID,
        DEFAULT_GITHUB_WEB_ORIGIN,
    )
    assert github_org_saml_service_provider_id("acme") == "github:saml:sp:org:acme"
    assert (
        github_enterprise_saml_service_provider_id("acme")
        == "github:saml:sp:enterprise:acme"
    )


def test_ghes_deployment_scopes_contract_ids_and_routes() -> None:
    deployment_id, web_origin = github_deployment_context(
        "https://api.github.example.com"
    )

    assert deployment_id == "api.github.example.com"
    assert web_origin == "https://api.github.example.com"
    assert (
        github_org_saml_service_provider_id("acme", deployment_id)
        == "github:api.github.example.com:saml:sp:org:acme"
    )
    assert github_org_acs_url("acme", web_origin) == (
        "https://api.github.example.com/orgs/acme/saml/consume"
    )
    assert github_enterprise_acs_url("acme", web_origin) == (
        "https://api.github.example.com/enterprises/acme/saml/consume"
    )


@pytest.mark.parametrize("host", ["github.example.com", "ftp://github.example.com"])
def test_github_deployment_context_rejects_invalid_hosts(host: str) -> None:
    with pytest.raises(ValueError):
        github_deployment_context(host)


def test_saml_match_helpers_preserve_source_exact_values() -> None:
    attributes = [
        {"name": ENTRA_OBJECT_ID_CLAIM, "value": "object-1"},
        SimpleNamespace(name=ENTRA_OBJECT_ID_CLAIM, value="object-1"),
        {"name": ENTRA_OBJECT_ID_CLAIM, "value": " object-2 "},
        {"name": "other", "value": "ignored"},
    ]

    assert saml_account_match_values(" Alice@example.com ", "", None, "Alice@example.com") == [
        "Alice@example.com"
    ]
    assert saml_attribute_match_values(attributes, ENTRA_OBJECT_ID_CLAIM) == [
        "object-1",
        "object-2",
    ]
