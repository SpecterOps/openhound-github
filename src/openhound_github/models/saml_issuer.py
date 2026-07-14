from dataclasses import dataclass

from openhound.core.asset import BaseAsset, NodeDef, EdgeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import nodes as nk
from openhound_github.kinds import edges as ek
from openhound_github.main import app

from .saml_helpers import (
    build_issuer_node_id,
    build_service_provider_node_id,
    normalize_scope_type,
)

@dataclass
class SAMLIssuerProperties(GHNodeProperties):
    """Properties for a normalized GitHub trusted SAML issuer.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        entity_id: The trusted SAML issuer entity ID.
    """
    native_id: str | None = None
    scope_type: str | None = None
    scope_slug: str | None = None
    entity_id: str | None = None

@app.asset(
    node=NodeDef(
        kind=nk.SAML_ISSUER,
        description="Normalized SAML issuer derived from GitHub SAML configuration",
        icon="id-badge",
        properties=SAMLIssuerProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SAML_SERVICE_PROVIDER,
            end=nk.SAML_ISSUER,
            kind=ek.SAML_TRUSTS_ISSUER,
            description="Normalized SAML service provider trusts this issuer",
            traversable=False,
        ),
    ],
)
class SamlIssuer(BaseAsset):
    issuer: str
    environment_slug: str
    environment_type: str
    environment_node_id: str | None = None
    environment_name: str | None = None

    @property
    def node_id(self) -> str | None:
        return build_issuer_node_id(self.issuer)
    
    @property
    def service_provider_node_id(self) -> str:
        return build_service_provider_node_id(
            self.environment_type,
            self.environment_slug,
        )

    @property
    def as_node(self) -> GHNode:
        scope_type = normalize_scope_type(self.environment_type)

        return GHNode(
            kinds=[nk.SAML_ISSUER],
            properties=SAMLIssuerProperties(
                name=self.node_id,
                displayname=self.issuer,
                node_id=self.node_id,
                entity_id=self.issuer,
                environmentid=self.environment_node_id,
                native_id=self.environment_node_id,
                scope_type=scope_type,
                scope_slug=self.environment_slug,
            ),
        )
    
    @property
    def edges(self):
        if self.issuer:
            yield Edge(
                kind=ek.SAML_TRUSTS_ISSUER,
                start=EdgePath(value=self.service_provider_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )