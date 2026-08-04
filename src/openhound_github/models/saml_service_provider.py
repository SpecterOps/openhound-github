from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    SAML_CONTRACT_VERSION,
    SAMLRelationshipEdgeProperties,
    github_saml_issuer_id,
    github_saml_route,
    github_saml_service_provider_id,
    normalize_scope_type,
)

@dataclass
class SAMLServiceProviderProperties(GHNodeProperties):
    """Properties for a normalized GitHub SAML service provider.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        saml_provider_id: The native GitHub SAML provider node ID.
        enabled: Whether SAML is enabled for the scope.
        entity_id: The SAML service provider entity ID.
        environment_name: The name of the GitHub organization or enterprise.
        github_deployment_id: Stable GitHub deployment identifier.
        github_web_origin: Browser origin for the GitHub deployment.
        schema_contract_version: Shared OpenGraph SAML contract version.
    """

    native_id: str | None = None
    scope_type: str | None = None
    scope_slug: str | None = None
    saml_provider_id: str | None = None
    enabled: bool | None = None
    entity_id: str | None = None
    environment_name: str | None = None
    github_deployment_id: str | None = None
    github_web_origin: str | None = None
    schema_contract_version: str = SAML_CONTRACT_VERSION

@app.asset(
    node=NodeDef(
        kind=nk.SAML_SERVICE_PROVIDER,
        description="Normalized SAML service provider derived from GitHub SAML configuration",
        icon="id-badge",
        properties=SAMLServiceProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SAML_IDENTITY_PROVIDER,
            end=nk.SAML_SERVICE_PROVIDER,
            kind=ek.SAML_IMPLEMENTS,
            description="GitHub native SAML configuration implements a normalized SAML service provider",
            traversable=False,
        ),
    ],
)

class SamlServiceProvider(BaseAsset):
    id: str
    issuer: str | None = None
    environment_node_id: str
    environment_name: str
    environment_slug: str
    environment_type: str
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def service_provider_node_id(self) -> str:
        return github_saml_service_provider_id(
            self.environment_type,
            self.environment_slug,
            self.github_deployment_id,
        )

    @property
    def issuer_node_id(self) -> str | None:
        if not self.issuer:
            return None
        return github_saml_issuer_id(
            self.environment_type,
            self.environment_slug,
            self.github_deployment_id,
        )

    @property
    def saml_route(self) -> tuple[str, str]:
        return github_saml_route(
            self.environment_type,
            self.environment_slug,
            self.github_web_origin,
        )

    @property
    def as_node(self) -> GHNode:
        _, sp_entity_id = self.saml_route
        scope_type = normalize_scope_type(self.environment_type)
        return GHNode(
            kinds=[nk.SAML_SERVICE_PROVIDER],
            properties=SAMLServiceProviderProperties(
                name=self.service_provider_node_id,
                displayname=self.environment_name,
                node_id=self.service_provider_node_id,
                entity_id=sp_entity_id,
                environment_name=self.environment_name,
                environmentid=self.environment_node_id,
                native_id=self.environment_node_id,
                scope_type=scope_type,
                scope_slug=self.environment_slug,
                saml_provider_id=self.id,
                enabled=True,
                github_deployment_id=self.github_deployment_id,
                github_web_origin=self.github_web_origin,
                schema_contract_version=SAML_CONTRACT_VERSION,
            ),
        )
    
    @property
    def edges(self):
        yield Edge(
            kind=ek.SAML_IMPLEMENTS,
            start=EdgePath(value=self.id, match_by="id"),
            end=EdgePath(value=self.service_provider_node_id, match_by="id"),
            properties=SAMLRelationshipEdgeProperties(traversable=False),
        )
