from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath
from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.saml_entity_panel_queries import (
    ENTITY_PANEL_QUERY_VERSION,
    node_entity_panel_queries,
)

from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    SAML_CONTRACT_VERSION,
    SAMLRelationshipEdgeProperties,
    github_saml_acs_id,
    github_saml_route,
    github_saml_service_provider_id,
    normalize_scope_type,
)

@dataclass
class SAMLAssertionConsumerServiceProperties(GHNodeProperties):
    """Properties for a normalized GitHub ACS route.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        acs_url: The byte-exact GitHub ACS URL.
        sp_entity_id: The byte-exact GitHub service provider entity ID.
        github_deployment_id: Stable GitHub deployment identifier.
        github_web_origin: Browser origin for the GitHub deployment.
        route_source: Convention used to derive the ACS route.
        schema_contract_version: Shared OpenGraph SAML contract version.
        entity_panel_query_version: Entity-panel query contract version.
        query_federation_providers: Query for providers using this endpoint.
        query_service_providers: Query for service providers using this endpoint.
    """
    native_id: str | None = None
    scope_type: str | None = None
    scope_slug: str | None = None
    acs_url: str | None = None
    sp_entity_id: str | None = None
    github_deployment_id: str | None = None
    github_web_origin: str | None = None
    route_source: str | None = None
    schema_contract_version: str = SAML_CONTRACT_VERSION
    entity_panel_query_version: str | None = None
    query_federation_providers: str | None = None
    query_service_providers: str | None = None

@app.asset(
    node=NodeDef(
        kind=nk.SAML_ASSERTION_CONSUMER_SERVICE,
        description="Normalized SAML assertion consumer service derived from GitHub SAML configuration",
        icon="id-badge",
        properties=SAMLAssertionConsumerServiceProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SAML_SERVICE_PROVIDER,
            end=nk.SAML_ASSERTION_CONSUMER_SERVICE,
            kind=ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE,
            description="Normalized SAML service provider has this assertion consumer service",
            traversable=False,
        ),
    ],
)
class SamlAssertionConsumerService(BaseAsset):
    environment_slug: str
    environment_type: str
    environment_node_id: str | None = None
    environment_name: str | None = None
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
    def saml_route(self) -> tuple[str, str]:
        return github_saml_route(
            self.environment_type,
            self.environment_slug,
            self.github_web_origin,
        )

    @property
    def node_id(self) -> str:
        return github_saml_acs_id(
            self.environment_type,
            self.environment_slug,
            self.github_deployment_id,
        )

    @property
    def as_node(self) -> GHNode:
        acs_url, sp_entity_id = self.saml_route
        scope_type = normalize_scope_type(self.environment_type)

        return GHNode(
            kinds=[nk.SAML_ASSERTION_CONSUMER_SERVICE],
            properties=SAMLAssertionConsumerServiceProperties(
                name=self.node_id,
                displayname=acs_url,
                node_id=self.node_id,
                acs_url=acs_url,
                sp_entity_id=sp_entity_id,
                environmentid=self.environment_node_id,
                native_id=self.environment_node_id,
                scope_type=scope_type,
                scope_slug=self.environment_slug,
                github_deployment_id=self.github_deployment_id,
                github_web_origin=self.github_web_origin,
                route_source=f"github_{scope_type}_scope_convention",
                schema_contract_version=SAML_CONTRACT_VERSION,
                entity_panel_query_version=ENTITY_PANEL_QUERY_VERSION,
                **node_entity_panel_queries(
                    nk.SAML_ASSERTION_CONSUMER_SERVICE, self.node_id
                ),
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE,
            start=EdgePath(value=self.service_provider_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=SAMLRelationshipEdgeProperties(traversable=False),
        )
