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


@dataclass
class GHEnterpriseSamlProviderProperties(GHNodeProperties):
    """Properties for an enterprise SAML identity provider.

    Attributes:
        issuer: The SAML issuer.
        sso_url: The SAML SSO URL.
        signature_method: The SAML signature method.
        digest_method: The SAML digest method.
        idp_certificate: The IdP certificate.
        foreign_environment_id: The correlated foreign environment ID.
        environment_name: The enterprise environment name.
        query_environments: Query for owning environments.
        query_external_identities: Query for external identities.
    """

    issuer: str | None = None
    sso_url: str | None = None
    signature_method: str | None = None
    digest_method: str | None = None
    idp_certificate: str | None = None
    foreign_environment_id: str | None = None
    environment_name: str | None = None
    query_environments: str | None = None
    query_external_identities: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.SAML_IDENTITY_PROVIDER,
        description="GitHub Enterprise SAML Identity Provider",
        icon="id-badge",
        properties=GHEnterpriseSamlProviderProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.SAML_IDENTITY_PROVIDER,
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            description="Enterprise uses this SAML IdP",
            traversable=False,
        ),
    ],
)
class EnterpriseSamlProvider(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    issuer: str | None = None
    sso_url: str | None = Field(alias="ssoUrl", default=None)
    digest_method: str | None = Field(alias="digestMethod", default=None)
    signature_method: str | None = Field(alias="signatureMethod", default=None)
    idp_certificate: str | None = Field(alias="idpCertificate", default=None)
    enterprise_node_id: str
    enterprise_slug: str

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    @property
    def node_id(self) -> str:
        return self.id

    @staticmethod
    def detect_foreign_environment(
        issuer: str | None, sso_url: str | None
    ) -> tuple[str | None, str | None]:
        if not issuer:
            return None, None
        if issuer.startswith("https://auth.pingone.com/"):
            return "PingOneUser", issuer.split("/")[3]
        if issuer.startswith("https://sts.windows.net/"):
            return "AZUser", issuer.split("/")[3]
        if issuer.startswith("http://www.okta.com/"):
            return "Okta_User", sso_url.split("/")[2] if sso_url else None
        return None, None

    @property
    def as_node(self) -> GHNode:
        _, foreign_environment_id = self.detect_foreign_environment(
            self.issuer, self.sso_url
        )
        return GHNode(
            kinds=[nk.SAML_IDENTITY_PROVIDER],
            properties=GHEnterpriseSamlProviderProperties(
                name=self.node_id,
                displayname=self.enterprise_slug,
                node_id=self.node_id,
                environmentid=self._lookup.enterprise_id(),
                environment_name=self.enterprise_slug,
                issuer=self.issuer,
                sso_url=self.sso_url,
                signature_method=self.signature_method,
                digest_method=self.digest_method,
                idp_certificate=self.idp_certificate,
                foreign_environment_id=foreign_environment_id,
                query_environments=f"MATCH p=(:GH_SamlIdentityProvider {{node_id:'{self.node_id}'}})<-[:GH_HasSamlIdentityProvider]-(:GH_Enterprise) RETURN p",
                query_external_identities=f"MATCH p=(:GH_SamlIdentityProvider {{node_id:'{self.node_id}'}})-[:GH_HasExternalIdentity]->() RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_SAML_IDENTITY_PROVIDER,
            start=EdgePath(value=self._lookup.enterprise_id(), match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
