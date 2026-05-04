from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


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
    query_environments: str | None = None
    query_external_identities: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.SAML_IDENTITY_PROVIDER,
        description="GitHub Organization SAML Identity Provider",
        icon="id-badge",
        properties=GHSamlProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.SAML_IDENTITY_PROVIDER,
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            description="Org uses this SAML IdP",
            traversable=False,
        ),
    ],
)
class SamlProvider(BaseAsset):
    """One record from `saml_provider` → one GH_SamlIdentityProvider node + GH_HasSamlIdentityProvider from org."""

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
    org_login: str
    org_name: str
    org_node_id: str  # organization.id (GraphQL global ID)

    @property
    def node_id(self) -> str:
        """The ID from a GraphQL API response is the same as a regular node_id"""
        return self.id

    @property
    def as_node(self) -> GHNode:
        iid = self.node_id
        return GHNode(
            kinds=[nk.SAML_IDENTITY_PROVIDER],
            properties=GHSamlProviderProperties(
                name=self.org_name,
                displayname=self.org_name,
                node_id=iid,
                issuer=self.issuer,
                sso_url=self.sso_url,
                signature_method=self.signature_method,
                digest_method=self.digest_method,
                idp_certificate=self.idp_certificate,
                environment_name=self.org_name,
                environmentid=self.org_node_id,
                foreign_environment_id=self.foreign_environment_id,
                query_environments=f"MATCH p=(:GH_SamlIdentityProvider {{node_id:'{iid}'}})<-[:GH_HasSamlIdentityProvider]-(:GH_Organization) RETURN p",
                query_external_identities=f"MATCH p=(:GH_SamlIdentityProvider {{node_id:'{iid}'}})-[:GH_HasExternalIdentity]->() RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
