from dataclasses import dataclass, field

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    Edge,
    EdgePath,
    EdgeProperties,
)
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    ENTRA_OBJECT_ID_CLAIM,
    SAML_CONTRACT_VERSION,
    github_saml_service_provider_id,
    saml_account_match_values,
    saml_attribute_match_values,
)


@dataclass
class SAMLHasAccountEdgeProperties(EdgeProperties):
    schema_contract_version: str = SAML_CONTRACT_VERSION
    match_values: list[str] = field(default_factory=list)
    scoped_exact_match_values: list[str] = field(default_factory=list)
    entra_object_id_match_values: list[str] = field(default_factory=list)
    direct_binding: bool = False
    direct_binding_source: str | None = None
    external_identity_id: str | None = None
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
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        display_name = (
            self.saml_identity.username
            if self.saml_identity and self.saml_identity.username
            else self.scim_identity.username
            if self.scim_identity and self.scim_identity.username
            else self.guid or self.node_id
        )

        return GHNode(
            kinds=[nk.EXTERNAL_IDENTITY],
            properties=GHExternalIdentityProperties(
                name=display_name,
                displayname=display_name,
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
                "environment_type": None,
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
    def service_provider_node_id(self) -> str | None:
        return github_saml_service_provider_id(
            self.idp.get("environment_type"),
            self.environment_slug,
            self.github_deployment_id,
        )

    @property
    def saml_scoped_exact_match_values(self) -> list[str]:
        if not self.saml_identity:
            return []
        return saml_account_match_values(
            self.saml_identity.username,
            self.saml_identity.name_id,
        )

    @property
    def enterprise_managed_user_scim_match_values(self) -> list[str]:
        if self.idp.get("environment_type") != "enterprise":
            return []
        if self.saml_scoped_exact_match_values or not self.scim_identity:
            return []
        return saml_account_match_values(self.scim_identity.username)

    @property
    def scoped_exact_match_values(self) -> list[str]:
        return (
            self.saml_scoped_exact_match_values
            or self.enterprise_managed_user_scim_match_values
        )

    @property
    def entra_object_id_match_values(self) -> list[str]:
        if not self.saml_identity:
            return []
        return saml_attribute_match_values(
            self.saml_identity.attributes,
            ENTRA_OBJECT_ID_CLAIM,
        )

    @property
    def saml_match_values(self) -> list[str]:
        return saml_account_match_values(
            *self.scoped_exact_match_values,
            *self.entra_object_id_match_values,
        )

    @property
    def saml_direct_binding_source(self) -> str | None:
        if self.saml_scoped_exact_match_values:
            return "GH_ExternalIdentity.saml_identity"
        if self.enterprise_managed_user_scim_match_values:
            return "GH_ExternalIdentity.scim_identity (Enterprise Managed Users)"
        return None

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
                    scoped_exact_match_values=self.scoped_exact_match_values,
                    entra_object_id_match_values=self.entra_object_id_match_values,
                    direct_binding=True,
                    direct_binding_source=self.saml_direct_binding_source,
                    external_identity_id=self.node_id,
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
