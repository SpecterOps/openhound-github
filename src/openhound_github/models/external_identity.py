from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    ConditionalEdgePath,
    Edge,
    EdgePath,
    EdgeProperties,
)
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_saml_provider import (
    EnterpriseSamlProvider,
    foreign_user_matchers,
)
from openhound_github.models.saml import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    ENTRA_OBJECT_ID_CLAIM,
    GithubSamlHasAccountProperties,
    github_org_saml_service_provider_id,
    saml_account_match_values,
    saml_attribute_match_values,
)


@dataclass
class GHExternalIdentityProperties(GHNodeProperties):
    """External identity properties and accordion panel queries.

    Attributes:
        guid: The GUID of the external identity.
        saml_identity_username: The username from the SAML identity.
        saml_identity_name_id: The SAML NameID attribute.
        saml_identity_given_name: The given name from the SAML identity.
        saml_identity_family_name: The family name from the SAML identity.
        scim_identity_username: The username from the SCIM identity.
        scim_identity_given_name: The given name from the SCIM identity.
        scim_identity_family_name: The family name from the SCIM identity.
        github_username: The GitHub login of the linked user.
        github_user_id: The GraphQL ID of the linked GitHub user.
        environment_name: The name of the environment (GitHub organization).
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


class SCIMIdentity(BaseModel):
    family_name: str | None = Field(alias="FamilyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    username: str | None = None


class SAMLIdentity(BaseModel):
    family_name: str | None = Field(alias="FamilyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    name_id: str | None = Field(alias="nameId", default=None)
    username: str | None = None
    attributes: list[dict[str, object]] = Field(default_factory=list)


class User(BaseModel):
    id: str
    login: str


@app.asset(
    node=NodeDef(
        kind=nk.EXTERNAL_IDENTITY,
        description="External IdP identity linked to a GitHub user",
        icon="arrows-left-right",
        properties=GHExternalIdentityProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SAML_IDENTITY_PROVIDER,
            end=nk.EXTERNAL_IDENTITY,
            kind=ek.HAS_EXTERNAL_IDENTITY,
            description="IdP has external identity",
            traversable=False,
        ),
        EdgeDef(
            start=nk.EXTERNAL_IDENTITY,
            end=nk.USER,
            kind=ek.MAPS_TO_USER,
            description="External identity maps to a user",
            traversable=False,
        ),
        EdgeDef(
            start=nk.EXTERNAL_IDENTITY,
            end=nk.USER,
            kind=ek.SYNCED_TO_GH_USER,
            description="Foreign IdP user is synced to a GitHub user",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SAML_SERVICE_PROVIDER,
            end=nk.USER,
            kind=ek.SAML_HAS_ACCOUNT,
            description="GitHub SAML service provider has a linked account",
            traversable=False,
        ),
    ],
)
class ExternalIdentity(BaseAsset):
    """One record from `external_identities` → one GH_ExternalIdentity node + mapping edges."""

    model_config = ConfigDict(populate_by_name=True)

    guid: str
    id: str
    saml_identity: SAMLIdentity = Field(alias="samlIdentity")
    scim_identity: SCIMIdentity | None = Field(alias="scimIdentity")
    user: User | None = None

    # Additional
    org_login: str
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:

        return GHNode(
            kinds=[nk.EXTERNAL_IDENTITY],
            properties=GHExternalIdentityProperties(
                name=self.guid or self.node_id,
                displayname=self.guid or self.node_id,
                node_id=self.node_id,
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
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_mapped_users=f"MATCH p=(:GH_ExternalIdentity {{node_id:'{self.node_id.upper()}'}})-[:GH_MapsToUser]->() RETURN p",
            ),
        )

    @property
    def idp(self) -> dict:
        ext_idp = self._lookup.idp_for_org(self.org_login)
        if not ext_idp:
            return {"id": None, "issuer": None, "sso_url": None}
        id, issuer, sso_url = ext_idp[0]
        return {
            "id": id,
            "issuer": issuer,
            "sso_url": sso_url,
        }

    @property
    def _maps_to_user_edges(self):
        if self.saml_identity:
            foreign_kind, foreign_env_id = (
                EnterpriseSamlProvider.detect_foreign_environment(
                    issuer=self.idp["issuer"],
                    sso_url=self.idp["sso_url"],
                )
            )
            foreign_username = self.saml_identity.username or (
                self.scim_identity.username if self.scim_identity else None
            )
            match_with = foreign_user_matchers(
                foreign_kind,
                foreign_env_id,
                foreign_username,
                self.saml_identity.attributes,
            )

            if foreign_kind and foreign_username and match_with:
                yield Edge(
                    kind=ek.MAPS_TO_USER,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=ConditionalEdgePath(
                        kind=foreign_kind, property_matchers=match_with
                    ),
                    properties=EdgeProperties(traversable=False),
                )

                # SyncedToGHUser: foreign IdP user → GitHub user
                gh_id = self.node_id.upper()
                q = (
                    f"MATCH p=()<-[:GH_SyncedToEnvironment]-(:GH_SamlIdentityProvider)"
                    f"-[:GH_HasExternalIdentity]->(:GH_ExternalIdentity)"
                    f"-[:GH_MapsToUser]->(n) "
                    f"WHERE n.objectid = '{gh_id}' OR n.name = '{foreign_username.upper()}' RETURN p"
                )
                yield Edge(
                    kind=ek.SYNCED_TO_GH_USER,
                    start=ConditionalEdgePath(
                        kind=foreign_kind, property_matchers=match_with
                    ),
                    end=EdgePath(value=self.node_id, match_by="id"),
                    properties=GHEdgeProperties(
                        traversable=True,
                        composed=True,
                        query_composition=q,
                    ),
                )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_EXTERNAL_IDENTITY,
            start=EdgePath(value=self.idp["id"], match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

        # GH_MapsToUser → linked GitHub user node (match by id)
        if self.user and self.user.id:
            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

        yield from self._maps_to_user_edges

        scoped_exact_match_values = saml_account_match_values(
            self.saml_identity.username if self.saml_identity else None,
            self.saml_identity.name_id if self.saml_identity else None,
        )
        entra_object_id_match_values = saml_attribute_match_values(
            self.saml_identity.attributes if self.saml_identity else [],
            ENTRA_OBJECT_ID_CLAIM,
        )
        match_values = saml_account_match_values(
            *scoped_exact_match_values,
            *entra_object_id_match_values,
        )
        if self.user and self.user.id and match_values:
            yield Edge(
                kind=ek.SAML_HAS_ACCOUNT,
                start=EdgePath(
                    value=github_org_saml_service_provider_id(
                        self.org_login, self.github_deployment_id
                    ),
                    match_by="id",
                ),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=GithubSamlHasAccountProperties(
                    traversable=False,
                    match_values=match_values,
                    scoped_exact_match_values=scoped_exact_match_values,
                    entra_object_id_match_values=entra_object_id_match_values,
                    direct_binding=True,
                    direct_binding_source="GH_ExternalIdentity.saml_identity",
                    external_identity_id=self.node_id,
                    account_state="unknown",
                ),
            )
