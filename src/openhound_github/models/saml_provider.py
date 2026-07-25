from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    detect_foreign_idp,
)


@dataclass
class GHSamlProviderProperties(GHNodeProperties):
    """SAML identity provider properties and accordion panel queries.
    
    Attributes:
        issuer: The SAML issuer URL.
        sso_url: The SAML single sign-on URL.
        signature_method: The signature method used by the SAML provider.
        digest_method: The digest method used by the SAML provider.
        idp_certificate: The identity provider's X.509 certificate.
        environment_name: The name of the environment (GitHub organization).
        foreign_environment_id: The ID of the foreign environment linked to this provider.
        query_environments: Query for environments.
        query_external_identities: Query for external identities.
    """

    issuer: str | None = None
    sso_url: str | None = None
    signature_method: str | None = None
    digest_method: str | None = None
    idp_certificate: str | None = None
    environment_name: str | None = None
    foreign_environment_id: str | None = None
    github_deployment_id: str | None = None
    github_web_origin: str | None = None
    query_environments: str | None = None
    query_external_identities: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.SAML_IDENTITY_PROVIDER,
        description="SAML Identity Provider for GitHub Organization or Enterprise Account",
        icon="id-badge",
        properties=GHSamlProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.SAML_IDENTITY_PROVIDER,
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            description="GitHub Organization uses this SAML IdP",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.SAML_IDENTITY_PROVIDER,
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            description="GitHub Enterprise Account uses this SAML IdP",
            traversable=False,
        ),
    ],
)
class SamlProvider(BaseAsset):
    """One record from `saml_provider` → one GH_SamlIdentityProvider node + GH_HasSamlIdentityProvider from org."""

    model_config = ConfigDict(populate_by_name=True)

    id: str

    digest_method: str | None = None
    idp_certificate: str | None = Field(default=None, alias="idpCertificate")
    issuer: str | None = None
    signature_method: str | None = Field(default=None, alias="signatureMethod")
    sso_url: str | None = Field(default=None, alias="ssoUrl")
    # Detected foreign IdP type and tenant, derived from issuer/sso_url
    # foreign_idp_type: str | None = None  # e.g. "entra", "okta", "pingone"
    foreign_environment_id: str | None = None  # tenant/org ID in the foreign IdP

    # Additional
    environment_node_id: str # organization.id (GraphQL global ID)
    environment_name: str
    environment_slug: str
    environment_type: str
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

    @property
    def node_id(self) -> str:
        """The ID from a GraphQL API response is the same as a regular node_id"""
        return self.id

    @property
    def as_node(self) -> GHNode:
        _, foreign_environment_id = detect_foreign_idp(self.issuer, self.sso_url)
        return GHNode(
            kinds=[nk.SAML_IDENTITY_PROVIDER],
            properties=GHSamlProviderProperties(
                name=self.node_id,
                displayname=self.environment_name,
                node_id=self.node_id,
                issuer=self.issuer,
                sso_url=self.sso_url,
                signature_method=self.signature_method,
                digest_method=self.digest_method,
                idp_certificate=self.idp_certificate,
                environment_name=self.environment_name,
                environmentid=self.environment_node_id,
                foreign_environment_id=foreign_environment_id,
                github_deployment_id=self.github_deployment_id,
                github_web_origin=self.github_web_origin,
                query_environments=f"MATCH p=(:GitHub)-[:GH_HasSamlIdentityProvider]->(:GH_SamlIdentityProvider {{node_id:'{self.node_id}'}}) RETURN p",
                query_external_identities=f"MATCH p=(:GH_SamlIdentityProvider {{node_id:'{self.node_id}'}})-[:GH_HasExternalIdentity]->(:GH_ExternalIdentity) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            start=EdgePath(value=self.environment_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
