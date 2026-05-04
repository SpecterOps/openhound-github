from dataclasses import dataclass, field

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

_FOREIGN_USER_KIND: dict[str, str] = {
    "entra": "AZUser",
    "okta": "OktaUser",
    "pingone": "PingOneUser",
}


@dataclass
class GHExternalIdentityProperties(GHNodeProperties):
    """External identity properties and accordion panel queries."""

    guid: str | None = field(
        default=None, metadata={"description": "The GUID of the external identity."}
    )
    saml_identity_username: str | None = field(
        default=None, metadata={"description": "The username from the SAML identity."}
    )
    saml_identity_name_id: str | None = field(
        default=None, metadata={"description": "The SAML NameID attribute."}
    )
    saml_identity_given_name: str | None = field(
        default=None, metadata={"description": "The given name from the SAML identity."}
    )
    saml_identity_family_name: str | None = field(
        default=None,
        metadata={"description": "The family name from the SAML identity."},
    )
    scim_identity_username: str | None = field(
        default=None, metadata={"description": "The username from the SCIM identity."}
    )
    scim_identity_given_name: str | None = field(
        default=None, metadata={"description": "The given name from the SCIM identity."}
    )
    scim_identity_family_name: str | None = field(
        default=None,
        metadata={"description": "The family name from the SCIM identity."},
    )
    github_username: str | None = field(
        default=None, metadata={"description": "The GitHub login of the linked user."}
    )
    github_user_id: str | None = field(
        default=None,
        metadata={"description": "The GraphQL ID of the linked GitHub user."},
    )
    environment_name: str = field(
        default="",
        metadata={"description": "The name of the environment (GitHub organization)."},
    )
    query_mapped_users: str = ""


class SCIMIdentity(BaseModel):
    family_name: str | None = Field(alias="FamilyName", default=None)
    given_name: str | None = Field(alias="givenName", default=None)
    username: str | None = None


class SAMLIdentity(BaseModel):
    family_name: str | None = Field(alias="FamilyName", default=None)
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
    ],
)
class ExternalIdentity(BaseAsset):
    """One record from `external_identities` → one GH_ExternalIdentity node + mapping edges."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    guid: str
    id: str
    saml_identity: SAMLIdentity = Field(alias="samlIdentity")
    scim_identity: SCIMIdentity | None = Field(alias="scimIdentity")
    user: User | None = None

    # Additional
    org_login: str

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

    @staticmethod
    def detect_foreign_idp(
        issuer: str | None, sso_url: str | None
    ) -> tuple[str | None, str | None]:
        """Detect the foreign IdP type and tenant/environment ID from the issuer or SSO URL."""
        if not issuer:
            return None, None
        if issuer.startswith("https://auth.pingone.com/"):
            return "pingone", issuer.split("/")[3]
        if issuer.startswith("https://sts.windows.net/"):
            return "entra", issuer.split("/")[3]
        if issuer.startswith("http://www.okta.com/"):
            domain = (sso_url or "").split("/")[2] if sso_url else None
            return "okta", domain
        return None, None

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
            foreign_idp_type, foreign_env_id = self.detect_foreign_idp(
                issuer=self.idp["issuer"],
                sso_url=self.idp["sso_url"],
            )
            foreign_kind = _FOREIGN_USER_KIND.get(foreign_idp_type or "", "")
            foreign_username = (
                self.saml_identity.username or self.scim_identity.username
            )

            # # GH_MapsToUser → foreign IdP user node (match by name)
            if foreign_kind and foreign_username:
                match_with = PropertyMatch(key="name", value=foreign_username)
                yield Edge(
                    kind=ek.MAPS_TO_USER,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=ConditionalEdgePath(
                        kind="User", property_matchers=[match_with]
                    ),
                    properties=EdgeProperties(traversable=False),
                )

            # SyncedToGHUser: foreign IdP user → GitHub user (traversable, with composition)
            if foreign_kind and foreign_username and self.node_id:
                match_with = PropertyMatch(key="name", value=foreign_username)

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
                        kind="User", property_matchers=[match_with]
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
