from dataclasses import dataclass
from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    Edge,
    EdgePath,
    EdgeProperties,
    PropertyMatch,
)
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.saml import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    DEFAULT_GITHUB_WEB_ORIGIN,
    ENTRA_OBJECT_ID_CLAIM,
    ENTRA_TENANT_ID_CLAIM,
    saml_attribute_match_values,
)


_FOREIGN_USER_ENVIRONMENT_PROPERTY: dict[str, str] = {
    nk.OKTA_USER: "tenant_domain",
    nk.PINGONE_USER: "environmentid",
}


def foreign_user_matchers(
    foreign_kind: str | None,
    foreign_environment_id: str | None,
    foreign_username: str | None,
    saml_attributes: list[Any] | None = None,
) -> list[PropertyMatch]:
    if foreign_kind == nk.AZ_USER:
        tenant_ids = saml_attribute_match_values(
            saml_attributes or [], ENTRA_TENANT_ID_CLAIM
        )
        object_ids = saml_attribute_match_values(
            saml_attributes or [], ENTRA_OBJECT_ID_CLAIM
        )
        if (
            not foreign_environment_id
            or len(tenant_ids) != 1
            or len(object_ids) != 1
            or tenant_ids[0].casefold() != foreign_environment_id.casefold()
        ):
            return []
        return [
            PropertyMatch(key="tenantid", value=tenant_ids[0].upper()),
            PropertyMatch(key="objectid", value=object_ids[0].upper()),
        ]

    environment_property = _FOREIGN_USER_ENVIRONMENT_PROPERTY.get(foreign_kind or "")
    if not environment_property or not foreign_environment_id or not foreign_username:
        return []
    return [
        PropertyMatch(key=environment_property, value=foreign_environment_id),
        PropertyMatch(key="name", value=foreign_username.upper()),
    ]


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
    github_deployment_id: str | None = None
    github_web_origin: str | None = None
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
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID
    github_web_origin: str = DEFAULT_GITHUB_WEB_ORIGIN

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
            return nk.PINGONE_USER, issuer.split("/")[3]
        if issuer.startswith("https://sts.windows.net/"):
            return nk.AZ_USER, issuer.split("/")[3]
        if issuer.startswith("http://www.okta.com/"):
            return nk.OKTA_USER, sso_url.split("/")[2] if sso_url else None
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
                github_deployment_id=self.github_deployment_id,
                github_web_origin=self.github_web_origin,
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
