from dataclasses import dataclass
from uuid import UUID

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    Edge,
    EdgePath,
    EdgeProperties,
)
from openhound_saml_producer import AccountFact, ServiceProviderFact, edge_defs
from openhound_saml_producer.contract import EdgeKind, NodeKind
from openhound_saml_producer.sp import service_provider_edges
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from .saml_producer import SAML, log_warnings, service_provider_fact

from .saml_helpers import (
    DEFAULT_GITHUB_DEPLOYMENT_ID,
    ENTRA_OBJECT_ID_CLAIM,
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


# The service provider asset declares the rest of the service provider edges.
_HAS_ACCOUNT_EDGE_DEFS = [
    edge_def
    for edge_def in edge_defs(
        NodeKind.SERVICE_PROVIDER,
        native_kind=nk.SAML_IDENTITY_PROVIDER,
        account_kinds=[nk.USER],
    )
    if edge_def.kind == EdgeKind.HAS_ACCOUNT.value
]


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


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
            start=nk.IDENTITY_PROVIDER,
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
        *_HAS_ACCOUNT_EDGE_DEFS,
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
    environment_node_id: str | None = None
    github_deployment_id: str = DEFAULT_GITHUB_DEPLOYMENT_ID

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        """Build the identity node, preferring its explicitly collected GitHub scope ID."""
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
                environmentid=self.environment_node_id
                or (self.idp["environment_node_id"] if self.idp else None),
                query_mapped_users=f"MATCH p=(:GH_ExternalIdentity {{node_id:'{self.node_id}'}})-[:GH_MapsToUser]->() RETURN p",
            ),
        )

    @property
    def idp(self) -> dict:
        ext_idp = self._lookup.identity_providers_for_environment(self.environment_slug)
        if len(ext_idp) != 1:
            return {
                "id": None,
                "issuer": None,
                "sso_url": None,
                "environment_node_id": None,
                "environment_name": None,
                "environment_type": None,
                "federation_type": None,
            }
        (
            provider_id, issuer, sso_url, environment_node_id,
            environment_name, environment_type, federation_type,
        ) = ext_idp[0]
        return {
            "id": provider_id,
            "issuer": issuer,
            "sso_url": sso_url,
            "environment_node_id": environment_node_id,
            "environment_name": environment_name,
            "environment_type": environment_type,
            "federation_type": federation_type,
        }

    @property
    def saml_service_provider_fact(self) -> ServiceProviderFact | None:
        """The service provider fact of this identity's SAML scope, if it has one."""
        idp = self.idp
        if idp.get("federation_type") != "saml":
            return None
        return service_provider_fact(
            saml_provider_id=idp["id"],
            environment_node_id=idp["environment_node_id"],
            environment_name=idp["environment_name"],
            environment_type=idp["environment_type"],
            environment_slug=self.environment_slug,
            github_deployment_id=self.github_deployment_id,
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
    def entra_object_id_claim_values(self) -> list[str]:
        """Every value of the Entra object ID attribute, source-exact."""
        if not self.saml_identity:
            return []
        return saml_attribute_match_values(
            self.saml_identity.attributes,
            ENTRA_OBJECT_ID_CLAIM,
        )

    @property
    def entra_object_id_match_values(self) -> list[str]:
        """The attribute values that are object IDs.

        The library accepts only a UUID in this typed list and rejects the fact
        otherwise, which would stop the whole conversion. A value that is not a
        UUID stays in `match_values` but is not typed as an object ID.
        """
        return [
            value
            for value in self.entra_object_id_claim_values
            if _is_uuid(value)
        ]

    @property
    def saml_match_values(self) -> list[str]:
        return saml_account_match_values(
            *self.scoped_exact_match_values,
            *self.entra_object_id_claim_values,
        )

    @property
    def saml_direct_binding_source(self) -> str | None:
        if self.saml_scoped_exact_match_values:
            return "GH_ExternalIdentity.saml_identity"
        if self.enterprise_managed_user_scim_match_values:
            return "GH_ExternalIdentity.scim_identity (Enterprise Managed Users)"
        return None

    def _saml_account_edges(self) -> list[Edge]:
        """Return `SAML_HasAccount` from the scope's service provider to the user.

        The library writes the edge. With no native object, issuer, or route, it
        writes nothing else, so the service provider asset owns those edges.
        """
        fact = self.saml_service_provider_fact
        match_values = self.saml_match_values
        if not (fact and self.user and self.user.id and match_values):
            return []
        scoped_exact = self.scoped_exact_match_values
        edges, warnings = service_provider_edges(
            SAML,
            fact,
            native=None,
            trusted_issuer=None,
            routes=[],
            accounts=[
                AccountFact(
                    account=EdgePath(value=self.user.id, match_by="id"),
                    native_object_id=self.user.id,
                    native_object_name=self.user.login,
                    match_values=match_values,
                    entra_object_id_match_values=self.entra_object_id_match_values,
                    scoped_exact_match_values=scoped_exact,
                    # The library needs scoped values to accept a direct binding.
                    direct_binding=bool(scoped_exact),
                    account_state="unknown",
                    extras={
                        "github_direct_binding_source": self.saml_direct_binding_source,
                        "github_external_identity_id": self.node_id,
                    },
                )
            ],
        )
        log_warnings(warnings)
        return edges

    @property
    def edges(self):
        if self.idp.get("id"):
            yield Edge(
                kind=ek.HAS_EXTERNAL_IDENTITY,
                start=EdgePath(value=self.idp["id"], match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

        yield from self._saml_account_edges()

        # GH_MapsToUser → linked GitHub user node (match by id)
        if self.user and self.user.id:
            yield Edge(
                kind=ek.MAPS_TO_USER,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.user.id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
