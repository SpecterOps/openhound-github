from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

@dataclass
class SAMLAssertionConsumerServiceProperties(GHNodeProperties):
    """Properties for a normalized GitHub ACS route.

    Attributes:
        native_id: The GitHub enterprise or organization node ID.
        scope_type: The GitHub SAML scope type.
        scope_slug: The GitHub enterprise or organization slug.
        acs_url: The byte-exact GitHub ACS URL.
        sp_entity_id: The byte-exact GitHub service provider entity ID.
    """
    native_id: str | None = None
    scope_type: str | None = None
    scope_slug: str | None = None
    acs_url: str | None = None
    sp_entity_id: str | None = None

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

    @property
    def service_provider_node_id(self) -> str:
        return f"saml:sp:github:{self.environment_type}:{self.environment_slug}"

    @property
    def saml_route(self) -> tuple[str, str]:
        if self.environment_type == "enterprise":
            base = f"https://github.com/enterprises/{self.environment_slug}"
        else:
            base = f"https://github.com/orgs/{self.environment_slug}"
        return f"{base}/saml/consume", base

    @property
    def node_id(self) -> str:
        acs_url, _ = self.saml_route
        return f"saml:acs:{acs_url}"

    @property
    def as_node(self) -> GHNode:
        acs_url, sp_entity_id = self.saml_route
        scope_type = "organization" if self.environment_type == "org" else self.environment_type

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
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.SAML_HAS_ASSERTION_CONSUMER_SERVICE,
            start=EdgePath(value=self.service_provider_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )