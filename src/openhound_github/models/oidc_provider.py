"""Enterprise OIDC provider metadata collected through GraphQL."""

from dataclasses import dataclass
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from .saml_helpers import DEFAULT_GITHUB_DEPLOYMENT_ID, DEFAULT_GITHUB_WEB_ORIGIN


@dataclass
class GHOidcProviderProperties(GHNodeProperties):
    """OIDC provider metadata and its enterprise collection context."""

    provider_type: str | None = None
    tenant_id: str | None = None
    environment_name: str | None = None
    github_deployment_id: str | None = None
    github_web_origin: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.OIDC_IDENTITY_PROVIDER,
        description="OIDC identity provider for a GitHub Enterprise account",
        icon="id-badge",
        properties=GHOidcProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.OIDC_IDENTITY_PROVIDER,
            kind=ek.HAS_OIDC_IDENTITY_PROVIDER,
            description="GitHub Enterprise account uses this OIDC identity provider",
            traversable=False,
        ),
    ],
)
class OidcProvider(BaseAsset):
    """Convert an enterprise OIDC provider and its containment relationship."""

    model_config = ConfigDict(populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: str
    provider_type: str = Field(alias="providerType")
    tenant_id: str = Field(alias="tenantId")
    environment_node_id: str
    environment_name: str
    environment_slug: str
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def node_id(self) -> str:
        """Return the provider's native GitHub identifier."""
        return self.id

    @property
    def as_node(self) -> GHNode:
        """Build the OIDC node with the shared identity-provider kind."""
        return GHNode(
            kinds=[nk.OIDC_IDENTITY_PROVIDER, nk.IDENTITY_PROVIDER],
            properties=GHOidcProviderProperties(
                name=self.node_id,
                displayname=self.environment_name,
                node_id=self.node_id,
                environmentid=self.environment_node_id,
                environment_name=self.environment_name,
                provider_type=self.provider_type,
                tenant_id=self.tenant_id,
                github_deployment_id=self.github_deployment_id,
                github_web_origin=self.github_web_origin,
            ),
        )

    @property
    def edges(self):
        """Link the enterprise to its provider through a non-traversable edge."""
        yield Edge(
            kind=ek.HAS_OIDC_IDENTITY_PROVIDER,
            start=EdgePath(value=self.environment_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
