from urllib.parse import urlparse

_FOREIGN_USER_KIND = {
    "entra": "AZUser",
    "okta": "Okta_User",
    "pingone": "PingOne_User",
}

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

def foreign_user_kind(foreign_idp_type: str | None) -> str:
    return _FOREIGN_USER_KIND.get(foreign_idp_type or "", "")

def build_service_provider_node_id(
    environment_type: str | None, 
    environment_slug: str | None
) -> str | None:
    if not environment_type or not environment_slug:
        return None
    return f"saml:sp:github:{environment_type}:{environment_slug}"

def build_issuer_node_id(issuer: str | None) -> str | None:
    if not issuer:
        return None
    return f"saml:trusted-issuer:{issuer}"

def build_saml_route(
    environment_type: str,
    environment_slug: str,
) -> tuple[str, str]:
    if environment_type == "enterprise":
        base = f"https://github.com/enterprises/{environment_slug}"
    else:
        base = f"https://github.com/orgs/{environment_slug}"
    return f"{base}/saml/consume", base

def normalize_scope_type(environment_type: str) -> str:
    return "organization" if environment_type == "org" else environment_type