from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

from openhound.core.models.entries_dataclass import EdgeProperties


SAML_CONTRACT_VERSION = "opengraph-saml-v0.3.0"
ENTRA_OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
DEFAULT_GITHUB_DEPLOYMENT_ID = "github.com"
DEFAULT_GITHUB_WEB_ORIGIN = "https://github.com"


@dataclass
class SAMLRelationshipEdgeProperties(EdgeProperties):
    schema_contract_version: str = SAML_CONTRACT_VERSION


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def detect_foreign_idp(
    issuer: str | None, sso_url: str | None
) -> tuple[str | None, str | None]:
    """Return the canonical foreign IdP type and tenant/environment identifier."""
    if not issuer:
        return None, None

    if issuer.startswith("https://auth.pingone.com/"):
        return "pingone", issuer.split("/")[3]

    if issuer.startswith("https://sts.windows.net/"):
        return "entra", issuer.split("/")[3]

    if issuer.startswith("http://www.okta.com/"):
        domain = urlparse(sso_url).netloc if sso_url else None
        return "okta", domain

    return None, None

def github_deployment_context(host: str) -> tuple[str, str]:
    """Return a stable deployment ID and browser origin for a GitHub API host."""
    parsed = urlparse(host)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("GitHub host must be an absolute HTTP(S) URL")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("GitHub host must use HTTP or HTTPS")

    hostname = parsed.hostname.lower()
    if hostname in {"api.github.com", "github.com"}:
        return DEFAULT_GITHUB_DEPLOYMENT_ID, DEFAULT_GITHUB_WEB_ORIGIN

    authority = hostname
    if parsed.port:
        authority = f"{authority}:{parsed.port}"
    return authority, f"{parsed.scheme.lower()}://{authority}"


def _saml_id(
    resource: str,
    scope_type: str,
    scope_slug: str,
    github_deployment_id: str,
) -> str:
    deployment_id = github_deployment_id.strip().lower()
    if deployment_id == DEFAULT_GITHUB_DEPLOYMENT_ID:
        return f"github:saml:{resource}:{scope_type}:{scope_slug}"
    encoded_deployment = quote(deployment_id, safe=".-_")
    return f"github:{encoded_deployment}:saml:{resource}:{scope_type}:{scope_slug}"


def github_enterprise_saml_service_provider_id(
    slug: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("sp", "enterprise", slug, github_deployment_id)


def github_enterprise_saml_issuer_id(
    slug: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("trusted-issuer", "enterprise", slug, github_deployment_id)


def github_enterprise_saml_acs_id(
    slug: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("acs", "enterprise", slug, github_deployment_id)


def github_enterprise_acs_url(
    slug: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> str:
    return f"{github_web_origin.rstrip('/')}/enterprises/{slug}/saml/consume"


def github_enterprise_sp_entity_id(
    slug: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> str:
    return f"{github_web_origin.rstrip('/')}/enterprises/{slug}"


def github_org_saml_service_provider_id(
    login: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("sp", "org", login, github_deployment_id)


def github_org_saml_issuer_id(
    login: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("trusted-issuer", "org", login, github_deployment_id)


def github_org_saml_acs_id(
    login: str,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str:
    return _saml_id("acs", "org", login, github_deployment_id)


def github_org_acs_url(
    login: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> str:
    return f"{github_web_origin.rstrip('/')}/orgs/{login}/saml/consume"


def github_org_sp_entity_id(
    login: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> str:
    return f"{github_web_origin.rstrip('/')}/orgs/{login}"


def github_saml_service_provider_id(
    environment_type: str | None,
    environment_slug: str | None,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str | None:
    if not environment_type or not environment_slug:
        return None
    if environment_type == "enterprise":
        return github_enterprise_saml_service_provider_id(
            environment_slug,
            github_deployment_id,
        )
    return github_org_saml_service_provider_id(
        environment_slug,
        github_deployment_id,
    )


def github_saml_issuer_id(
    environment_type: str | None,
    environment_slug: str | None,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str | None:
    if not environment_type or not environment_slug:
        return None
    if environment_type == "enterprise":
        return github_enterprise_saml_issuer_id(
            environment_slug,
            github_deployment_id,
        )
    return github_org_saml_issuer_id(
        environment_slug,
        github_deployment_id,
    )


def github_saml_acs_id(
    environment_type: str | None,
    environment_slug: str | None,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str | None:
    if not environment_type or not environment_slug:
        return None
    if environment_type == "enterprise":
        return github_enterprise_saml_acs_id(
            environment_slug,
            github_deployment_id,
        )
    return github_org_saml_acs_id(
        environment_slug,
        github_deployment_id,
    )


def github_saml_route(
    environment_type: str,
    environment_slug: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> tuple[str, str]:
    if environment_type == "enterprise":
        return (
            github_enterprise_acs_url(environment_slug, github_web_origin),
            github_enterprise_sp_entity_id(environment_slug, github_web_origin),
        )
    return (
        github_org_acs_url(environment_slug, github_web_origin),
        github_org_sp_entity_id(environment_slug, github_web_origin),
    )


def saml_account_match_values(*values: str | None) -> list[str]:
    """Return source-exact SAML account values with blank values removed."""
    return _dedupe(list(values))


def saml_attribute_match_values(
    attributes: list[Any], attribute_name: str
) -> list[str]:
    """Return source-exact values for one explicitly named SAML attribute."""
    values: list[str | None] = []
    for attribute in attributes:
        if isinstance(attribute, Mapping):
            name = attribute.get("name")
            value = attribute.get("value")
        else:
            name = getattr(attribute, "name", None)
            value = getattr(attribute, "value", None)
        if name == attribute_name:
            values.append(value)
    return _dedupe(values)


def build_service_provider_node_id(
    environment_type: str | None,
    environment_slug: str | None,
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID,
) -> str | None:
    return github_saml_service_provider_id(
        environment_type,
        environment_slug,
        github_deployment_id,
    )

def build_issuer_node_id(issuer: str | None) -> str | None:
    if not issuer:
        return None
    return f"saml:trusted-issuer:{issuer}"

def build_saml_route(
    environment_type: str,
    environment_slug: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> tuple[str, str]:
    return github_saml_route(
        environment_type,
        environment_slug,
        github_web_origin,
    )

def normalize_scope_type(environment_type: str) -> str:
    return "organization" if environment_type == "org" else environment_type
