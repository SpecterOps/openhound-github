from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    ConditionalEdgePath,
    Edge,
    EdgePath,
    EdgeProperties,
    PropertyMatch,
)
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_saml_provider import EnterpriseSamlProvider


class EnterpriseIdentityName(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    family_name: str | None = Field(alias="familyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    name_id: str | None = Field(alias="nameId", default=None)
    username: str | None = None


class EnterpriseIdentityUser(BaseModel):
    id: str
    login: str


@dataclass
class GHEnterpriseExternalIdentityProperties(GHNodeProperties):
    """Properties for an enterprise external identity.

    Attributes:
        guid: The external identity GUID.
        saml_identity_username: The SAML username.
        saml_identity_name_id: The SAML NameID.
        saml_identity_given_name: The SAML given name.
        saml_identity_family_name: The SAML family name.
        scim_identity_username: The SCIM username.
        scim_identity_given_name: The SCIM given name.
        scim_identity_family_name: The SCIM family name.
        github_username: The mapped GitHub username.
        github_user_id: The mapped GitHub user node ID.
        environment_name: The enterprise environment name.
        query_mapped_users: Query for mapped users.
    """

    guid: str | None = None
    saml_identity_username: str | None = None
    saml_identity_name_id: str | None = None
    saml_identity_given_name: str | None = None
    saml_identity_family_name: str | None = None
    scim_identity_username: str | None = None
    scim_identity_given_name: str | None = None
    scim_identity_family_name: str | None = None
    github_username: str | None = None
    github_user_id: str | None = None
    environment_name: str | None = None
    query_mapped_users: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.EXTERNAL_IDENTITY,
        description="GitHub Enterprise External Identity",
        icon="arrows-left-right",
        properties=GHEnterpriseExternalIdentityProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SAML_IDENTITY_PROVIDER,
            end=nk.EXTERNAL_IDENTITY,
            kind=ek.HAS_EXTERNAL_IDENTITY,
            description="Enterprise IdP has external identity",
            traversable=False,
        ),
        EdgeDef(
            start=nk.EXTERNAL_IDENTITY,
            end=nk.USER,
            kind=ek.MAPS_TO_USER,
            description="External identity maps to GitHub user",
            traversable=False,
        ),
    ],
)
class EnterpriseExternalIdentity(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    guid: str | None = None
    id: str
    saml_identity: EnterpriseIdentityName | None = Field(
        alias="samlIdentity", default=None
    )
    scim_identity: EnterpriseIdentityName | None = Field(
        alias="scimIdentity", default=None
    )
    user: EnterpriseIdentityUser | None = None
    saml_provider_id: str
    saml_provider_issuer: str | None = None
    saml_provider_sso_url: str | None = None
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def foreign_user(self) -> tuple[str | None, str | None]:
        return EnterpriseSamlProvider.detect_foreign_environment(
            self.saml_provider_issuer, self.saml_provider_sso_url
        )

    @property
    def foreign_username(self) -> str | None:
        if self.saml_identity and self.saml_identity.username:
            return self.saml_identity.username
        if self.scim_identity and self.scim_identity.username:
            return self.scim_identity.username
        return None

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.EXTERNAL_IDENTITY],
            properties=GHEnterpriseExternalIdentityProperties(
                name=self.guid or self.node_id,
                displayname=self.guid or self.node_id,
                node_id=self.node_id,
                environmentid=self._lookup.enterprise_id(),
                environment_name=self.enterprise_slug,
                guid=self.guid,
                saml_identity_username=self.saml_identity.username
                if self.saml_identity
                else None,
                saml_identity_name_id=self.saml_identity.name_id
                if self.saml_identity
                else None,
                saml_identity_given_name=self.saml_identity.given_name
                if self.saml_identity
                else None,
                saml_identity_family_name=self.saml_identity.family_name
                if self.saml_identity
                else None,
                scim_identity_username=self.scim_identity.username
                if self.scim_identity
                else None,
                scim_identity_given_name=self.scim_identity.given_name
                if self.scim_identity
                else None,
                scim_identity_family_name=self.scim_identity.family_name
                if self.scim_identity
                else None,
                github_username=self.user.login if self.user else None,
                github_user_id=self.user.id if self.user else None,
                query_mapped_users=f"MATCH p=(:GH_ExternalIdentity {{node_id:'{self.node_id}'}})-[:GH_MapsToUser]->() RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_EXTERNAL_IDENTITY,
            start=EdgePath(value=self.saml_provider_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        if self.user and self.user.id:
            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

        foreign_kind, _ = self.foreign_user
        if foreign_kind and self.foreign_username:
            match = PropertyMatch(key="name", value=self.foreign_username)
            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=foreign_kind,
                    property_matchers=[match],
                ),
                properties=EdgeProperties(traversable=False),
            )
            if self.user and self.user.id:
                yield Edge(
                    kind=ek.SYNCED_TO_GH_USER,
                    start=ConditionalEdgePath(
                        kind=foreign_kind,
                        property_matchers=[match],
                    ),
                    end=EdgePath(value=self.user.id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )
