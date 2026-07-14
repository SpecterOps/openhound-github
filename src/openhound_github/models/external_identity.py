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

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

from .saml_helpers import (
    build_service_provider_node_id,
    detect_foreign_idp,
    foreign_user_kind,
)

@dataclass
class SAMLHasAccountEdgeProperties(EdgeProperties):
    match_values: list[str] | None = None
    account_state: str = "unknown"

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
        environment_name: The name of the environment (GitHub organization or enterprise).
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
    family_name: str | None = Field(alias="familyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    username: str | None = None


class SAMLIdentity(BaseModel):
    family_name: str | None = Field(alias="familyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    name_id: str | None = Field(alias="nameId", default=None)
    username: str | None = None


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
            description="Normalized SAML service provider has this downstream GitHub account",
            traversable=False,
        ),
    ],
)
class ExternalIdentity(BaseAsset):
    """One record from `external_identities` → one GH_ExternalIdentity node + mapping edges."""

    model_config = ConfigDict(populate_by_name=True)

    guid: str
    id: str
    saml_identity: SAMLIdentity | None = Field(alias="samlIdentity", default=None)
    scim_identity: SCIMIdentity | None = Field(alias="scimIdentity", default=None)
    user: User | None = None

    # Additional
    environment_slug: str

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
                environment_name=self.idp["environment_name"] if self.idp else None,
                environmentid=self.idp["environment_node_id"] if self.idp else None,
                query_mapped_users=f"MATCH p=(:GH_ExternalIdentity {{node_id:'{self.node_id}'}})-[:GH_MapsToUser]->() RETURN p",
            ),
        )

    @property
    def idp(self) -> dict:
        ext_idp = self._lookup.idp_for_environment(self.environment_slug)
        if not ext_idp:
            return {
                "id": None,
                "issuer": None,
                "sso_url": None,
                "environment_node_id": None,
                "environment_name": None,
            }
        provider_id, issuer, sso_url, environment_node_id, environment_name, environment_type = ext_idp[0]
        return {
            "id": provider_id,
            "issuer": issuer,
            "sso_url": sso_url,
            "environment_node_id": environment_node_id,
            "environment_name": environment_name,
            "environment_type": environment_type,
        }

    @property
    def _maps_to_user_edges(self):
        foreign_idp_type, foreign_env_id = detect_foreign_idp(
            issuer=self.idp["issuer"],
            sso_url=self.idp["sso_url"],
        )
        foreign_kind = foreign_user_kind(foreign_idp_type)

        foreign_env_key = None
        if foreign_idp_type == "okta":
            foreign_env_key = "tenant_domain"
        elif foreign_idp_type == "pingone":
            foreign_env_key = "environmentid"
        elif foreign_idp_type == "entra":
            foreign_env_key = "tenantid"

        foreign_username = None
        if self.saml_identity and self.saml_identity.name_id:
            foreign_username = self.saml_identity.name_id
        elif self.saml_identity and self.saml_identity.username:
            foreign_username = self.saml_identity.username
        elif self.scim_identity and self.scim_identity.username:
            foreign_username = self.scim_identity.username

        match_key = "name"
        if foreign_idp_type == "pingone":
            match_key = "email"
        elif foreign_idp_type == "okta":
            match_key = "login"

        # # GH_MapsToUser → foreign IdP user node (match by name)
        matchers = None
        if foreign_kind and foreign_username:
            matchers = [PropertyMatch(key=match_key, value=foreign_username)]
            if foreign_env_key and foreign_env_id:
                matchers.append(
                    PropertyMatch(key=foreign_env_key, value=foreign_env_id)
                )

            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=foreign_kind, 
                    property_matchers=matchers
                ),
                properties=EdgeProperties(traversable=False),
            )

        # SyncedToGHUser: foreign IdP user → GitHub user (traversable, with composition)
        if matchers and self.user and self.user.id:
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
                    kind=foreign_kind,
                    property_matchers=matchers
                ),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    query_composition=q,
                ),
            )

    @property
    def service_provider_node_id(self) -> str | None:
        return build_service_provider_node_id(
            self.idp.get("environment_type"),
            self.environment_slug,
        )

    @property
    def saml_match_values(self) -> list[str]:
        values = []

        if self.saml_identity and self.saml_identity.name_id:
            values.append(self.saml_identity.name_id)

        cleaned = []
        seen = set()
        for value in values:
            v = str(value).strip()
            if v and v not in seen:
                cleaned.append(v)
                seen.add(v)

        return cleaned

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_EXTERNAL_IDENTITY,
            start=EdgePath(value=self.idp["id"], match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

        has_idp = bool(self.idp.get("id"))
        service_provider_node_id = self.service_provider_node_id
        match_values = self.saml_match_values

        if has_idp and service_provider_node_id and self.user and self.user.id and match_values:
            yield Edge(
                kind=ek.SAML_HAS_ACCOUNT,
                start=EdgePath(value=service_provider_node_id, match_by="id"),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=SAMLHasAccountEdgeProperties(
                    traversable=False,
                    match_values=match_values,
                    account_state="unknown",
                ),
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
