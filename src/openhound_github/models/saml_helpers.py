from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse


ENTRA_OBJECT_ID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
DEFAULT_GITHUB_DEPLOYMENT_ID = "github.com"
DEFAULT_GITHUB_WEB_ORIGIN = "https://github.com"


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


def github_saml_route(
    environment_type: str,
    environment_slug: str,
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN,
) -> tuple[str, str]:
    """Return the ACS URL and service provider entity ID of a GitHub scope.

    GitHub derives both from the web origin and the scope: an enterprise or an
    organization.
    """
    origin = github_web_origin.rstrip("/")
    if environment_type == "enterprise":
        entity_id = f"{origin}/enterprises/{environment_slug}"
    else:
        entity_id = f"{origin}/orgs/{environment_slug}"
    return f"{entity_id}/saml/consume", entity_id


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


def normalize_scope_type(environment_type: str) -> str:
    return "organization" if environment_type == "org" else environment_type
