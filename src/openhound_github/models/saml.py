from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from typing import Any

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


SAML_CONTRACT_VERSION = "opengraph-saml-v0.3.0"
ENTRA_OBJECT_ID_CLAIM = (
    "http://schemas.microsoft.com/identity/claims/objectidentifier"
)


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


def _provider_field(provider: Any, field: str) -> Any:
    """Read a provider field from either a model or a DLT-replayed mapping."""
    if isinstance(provider, Mapping):
        return provider.get(field)
    return getattr(provider, field)


def github_enterprise_saml_service_provider_id(slug: str) -> str:
    return f"github:saml:sp:enterprise:{slug}"


def github_enterprise_saml_issuer_id(slug: str) -> str:
    return f"github:saml:trusted-issuer:enterprise:{slug}"


def github_enterprise_saml_acs_id(slug: str) -> str:
    return f"github:saml:acs:enterprise:{slug}"


def github_enterprise_acs_url(slug: str) -> str:
    return f"https://github.com/enterprises/{slug}/saml/consume"


def github_enterprise_sp_entity_id(slug: str) -> str:
    return f"https://github.com/enterprises/{slug}"


def github_org_saml_service_provider_id(login: str) -> str:
    return f"github:saml:sp:org:{login}"


def github_org_saml_issuer_id(login: str) -> str:
    return f"github:saml:trusted-issuer:org:{login}"


def github_org_saml_acs_id(login: str) -> str:
    return f"github:saml:acs:org:{login}"


def github_org_acs_url(login: str) -> str:
    return f"https://github.com/orgs/{login}/saml/consume"


def github_org_sp_entity_id(login: str) -> str:
    return f"https://github.com/orgs/{login}"


def enterprise_saml_service_provider_row(provider) -> dict[str, Any] | None:
    if not _clean(provider.issuer):
        return None
    slug = provider.enterprise_slug
    return {
        "id": github_enterprise_saml_service_provider_id(slug),
        "native_id": provider.enterprise_node_id,
        "scope_type": "enterprise",
        "scope_slug": slug,
        "saml_provider_id": provider.id,
        "issuer_id": github_enterprise_saml_issuer_id(slug),
        "acs_id": github_enterprise_saml_acs_id(slug),
        "enabled": True,
    }


def enterprise_saml_issuer_row(provider) -> dict[str, Any] | None:
    issuer = _clean(provider.issuer)
    if not issuer:
        return None
    slug = provider.enterprise_slug
    return {
        "id": github_enterprise_saml_issuer_id(slug),
        "native_id": provider.enterprise_node_id,
        "scope_type": "enterprise",
        "scope_slug": slug,
        "entity_id": issuer,
    }


def enterprise_saml_acs_row(provider) -> dict[str, Any] | None:
    if not _clean(provider.issuer):
        return None
    slug = provider.enterprise_slug
    return {
        "id": github_enterprise_saml_acs_id(slug),
        "native_id": provider.enterprise_node_id,
        "scope_type": "enterprise",
        "scope_slug": slug,
        "acs_url": github_enterprise_acs_url(slug),
        "sp_entity_id": github_enterprise_sp_entity_id(slug),
    }


def org_saml_service_provider_row(provider) -> dict[str, Any] | None:
    if not _clean(_provider_field(provider, "issuer")):
        return None
    login = _provider_field(provider, "org_login")
    return {
        "id": github_org_saml_service_provider_id(login),
        "native_id": _provider_field(provider, "org_node_id"),
        "scope_type": "organization",
        "scope_slug": login,
        "saml_provider_id": _provider_field(provider, "id"),
        "issuer_id": github_org_saml_issuer_id(login),
        "acs_id": github_org_saml_acs_id(login),
        "enabled": True,
    }


def org_saml_issuer_row(provider) -> dict[str, Any] | None:
    issuer = _clean(_provider_field(provider, "issuer"))
    if not issuer:
        return None
    login = _provider_field(provider, "org_login")
    return {
        "id": github_org_saml_issuer_id(login),
        "native_id": _provider_field(provider, "org_node_id"),
        "scope_type": "organization",
        "scope_slug": login,
        "entity_id": issuer,
    }


def org_saml_acs_row(provider) -> dict[str, Any] | None:
    if not _clean(_provider_field(provider, "issuer")):
        return None
    login = _provider_field(provider, "org_login")
    return {
        "id": github_org_saml_acs_id(login),
        "native_id": _provider_field(provider, "org_node_id"),
        "scope_type": "organization",
        "scope_slug": login,
        "acs_url": github_org_acs_url(login),
        "sp_entity_id": github_org_sp_entity_id(login),
    }


def saml_account_match_values(*values: str | None) -> list[str]:
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


@dataclass
class GithubSamlServiceProviderProperties(GHNodeProperties):
    """Properties for a normalized GitHub SAML service provider.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        saml_provider_id: The native GitHub SAML provider node ID.
        enabled: Whether SAML is enabled for the scope.
    """

    native_id: str
    scope_type: str
    scope_slug: str
    saml_provider_id: str
    enabled: bool
    schema_contract_version: str


@dataclass
class GithubSamlIssuerProperties(GHNodeProperties):
    """Properties for a normalized GitHub trusted SAML issuer.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        entity_id: The trusted SAML issuer entity ID.
    """

    native_id: str
    scope_type: str
    scope_slug: str
    entity_id: str
    native_source_field: str
    schema_contract_version: str


@dataclass
class GithubSamlAssertionConsumerServiceProperties(GHNodeProperties):
    """Properties for a normalized GitHub ACS route.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        acs_url: The byte-exact GitHub ACS URL.
        sp_entity_id: The byte-exact GitHub service provider entity ID.
    """

    native_id: str
    scope_type: str
    scope_slug: str
    acs_url: str
    sp_entity_id: str
    route_source: str
    schema_contract_version: str


@dataclass
class GithubSamlRelationshipProperties(EdgeProperties):
    """Fact-local contract metadata for normalized SAML topology."""

    schema_contract_version: str = SAML_CONTRACT_VERSION


@dataclass
class GithubSamlHasAccountProperties(EdgeProperties):
    """Properties for a normalized GitHub SAML account edge.

    Attributes:
        match_values: Source-exact SAML external-identity values for the account.
        scoped_exact_match_values: Route-scoped canonical direct-binding values.
        entra_object_id_match_values: Explicit Microsoft objectidentifier claim
            values observed on the linked SAML identity.
        direct_binding: Whether GitHub already resolved these values to the account.
        account_state: The account state when known.
    """

    schema_contract_version: str = SAML_CONTRACT_VERSION
    match_values: list[str] = dc_field(default_factory=list)
    scoped_exact_match_values: list[str] = dc_field(default_factory=list)
    entra_object_id_match_values: list[str] = dc_field(default_factory=list)
    direct_binding: bool = False
    direct_binding_source: str | None = None
    external_identity_id: str | None = None
    account_state: str = "unknown"


@app.asset(
    node=NodeDef(
        icon="id-card",
        kind=nk.SAML_SERVICE_PROVIDER,
        description="Normalized GitHub SAML service provider",
        properties=GithubSamlServiceProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.SAML_SERVICE_PROVIDER,
            kind=ek.SAML_IMPLEMENTS,
            description="GitHub enterprise implements a normalized SAML service provider",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.SAML_SERVICE_PROVIDER,
            kind=ek.SAML_IMPLEMENTS,
            description="GitHub organization implements a normalized SAML service provider",
            traversable=False,
        ),
        EdgeDef(
            start=nk.SAML_SERVICE_PROVIDER,
            end=nk.SAML_ISSUER,
            kind=ek.SAML_TRUSTS_ISSUER,
            description="GitHub SAML service provider trusts an IdP issuer",
            traversable=False,
        ),
        EdgeDef(
            start=nk.SAML_SERVICE_PROVIDER,
            end=nk.SAML_ASSERTION_CONSUMER_SERVICE,
            kind=ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE,
            description="GitHub SAML service provider has an ACS route",
            traversable=False,
        ),
    ],
)
class GithubSamlServiceProvider(BaseAsset):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    native_id: str
    scope_type: str
    scope_slug: str
    saml_provider_id: str
    issuer_id: str
    acs_id: str
    enabled: bool

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.SAML_SERVICE_PROVIDER],
            properties=GithubSamlServiceProviderProperties(
                name=self.scope_slug,
                displayname=self.scope_slug,
                node_id=self.id,
                environmentid=self.native_id,
                native_id=self.native_id,
                scope_type=self.scope_type,
                scope_slug=self.scope_slug,
                saml_provider_id=self.saml_provider_id,
                enabled=self.enabled,
                schema_contract_version=SAML_CONTRACT_VERSION,
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.SAML_IMPLEMENTS,
            start=EdgePath(value=self.native_id, match_by="id"),
            end=EdgePath(value=self.id, match_by="id"),
            properties=GithubSamlRelationshipProperties(traversable=False),
        )
        yield Edge(
            kind=ek.SAML_TRUSTS_ISSUER,
            start=EdgePath(value=self.id, match_by="id"),
            end=EdgePath(value=self.issuer_id, match_by="id"),
            properties=GithubSamlRelationshipProperties(traversable=False),
        )
        yield Edge(
            kind=ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE,
            start=EdgePath(value=self.id, match_by="id"),
            end=EdgePath(value=self.acs_id, match_by="id"),
            properties=GithubSamlRelationshipProperties(traversable=False),
        )


@app.asset(
    node=NodeDef(
        icon="key-round",
        kind=nk.SAML_ISSUER,
        description="Normalized GitHub trusted SAML IdP issuer",
        properties=GithubSamlIssuerProperties,
    ),
)
class GithubSamlIssuer(BaseAsset):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    native_id: str
    scope_type: str
    scope_slug: str
    entity_id: str

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.SAML_ISSUER],
            properties=GithubSamlIssuerProperties(
                name=self.entity_id,
                displayname=self.entity_id,
                node_id=self.id,
                environmentid=self.native_id,
                native_id=self.native_id,
                scope_type=self.scope_type,
                scope_slug=self.scope_slug,
                entity_id=self.entity_id,
                native_source_field="GH_SamlIdentityProvider.issuer",
                schema_contract_version=SAML_CONTRACT_VERSION,
            ),
        )

    @property
    def edges(self):
        return iter(())


@app.asset(
    node=NodeDef(
        icon="route",
        kind=nk.SAML_ASSERTION_CONSUMER_SERVICE,
        description="Normalized GitHub SAML ACS route",
        properties=GithubSamlAssertionConsumerServiceProperties,
    ),
)
class GithubSamlAssertionConsumerService(BaseAsset):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    native_id: str
    scope_type: str
    scope_slug: str
    acs_url: str
    sp_entity_id: str

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.SAML_ASSERTION_CONSUMER_SERVICE],
            properties=GithubSamlAssertionConsumerServiceProperties(
                name=self.acs_url,
                displayname=self.acs_url,
                node_id=self.id,
                environmentid=self.native_id,
                native_id=self.native_id,
                scope_type=self.scope_type,
                scope_slug=self.scope_slug,
                acs_url=self.acs_url,
                sp_entity_id=self.sp_entity_id,
                route_source=f"github_{self.scope_type}_scope_convention",
                schema_contract_version=SAML_CONTRACT_VERSION,
            ),
        )

    @property
    def edges(self):
        return iter(())
