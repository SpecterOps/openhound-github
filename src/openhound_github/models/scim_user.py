"""Normalized SCIM graph assets emitted from GitHub SCIM APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import (
    ConditionalEdgePath,
    Edge,
    EdgePath,
    EdgeProperties,
    Node,
    NodeProperties,
    PropertyMatch,
)
from pydantic import BaseModel, ConfigDict, Field

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.saml_helpers import detect_foreign_idp

SCIM_SOURCE_KIND = "SCIM"


def scim_organization_id(scope_node_id: str) -> str:
    return f"SCIM_Organization_{scope_node_id}"


@dataclass
class ScimNodeProperties(NodeProperties):
    collected: bool = True
    external_id: str | None = None
    user_name: str | None = None
    enabled: bool | None = None
    given_name: str | None = None
    family_name: str | None = None
    mail: str | None = None
    profile_url: str | None = None
    enterprise: str | None = None
    organization: str | None = None


@dataclass
class ScimOrganizationNodeProperties(ScimNodeProperties):
    scim_base_url: str | None = None
    scope_type: str | None = None


@dataclass
class ScimUserNodeProperties(ScimNodeProperties):
    active: bool | None = None
    resource_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Preserve complete role and group objects using scalar graph properties.
    roles: str = "[]"
    groups: str = "[]"


@dataclass
class ScimGroupNodeProperties(ScimNodeProperties):
    resource_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Count returned entries; an omitted list does not establish zero members.
    member_count: int | None = None


@dataclass
class ScimNode(Node):
    id: str

    def __post_init__(self):
        if SCIM_SOURCE_KIND not in self.kinds:
            self.kinds.append(SCIM_SOURCE_KIND)


class Name(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    given_name: str | None = Field(default=None, alias="givenName")
    family_name: str | None = Field(default=None, alias="familyName")
    formatted: str | None = None


class ScimMeta(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    created: str | None = None
    last_modified: str | None = Field(default=None, alias="lastModified")
    location: str | None = None


def _primary_email(emails: list[dict[str, Any]]) -> str | None:
    for email in emails:
        if email.get("primary") is True and email.get("value"):
            return str(email["value"])
    for email in emails:
        if email.get("value"):
            return str(email["value"])
    return None


class ScimScopeAsset(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    enterprise_node_id: str | None = None
    enterprise_slug: str | None = None
    org_login: str | None = None
    org_node_id: str | None = None

    @property
    def scope_node_id(self) -> str:
        if self.enterprise_node_id:
            return self.enterprise_node_id
        if self.org_node_id:
            return self.org_node_id
        if self.org_login:
            resolved = self._lookup.org_id_for_login(self.org_login)
            if resolved:
                return resolved
        raise ValueError("SCIM asset has no resolvable GitHub scope node ID")

    @property
    def scope_name(self) -> str:
        return self.enterprise_slug or self.org_login or self.scope_node_id

    @property
    def scim_org_id(self) -> str:
        return scim_organization_id(self.scope_node_id)


@app.asset(
    node=NodeDef(
        kind=nk.SCIM_ORGANIZATION,
        description="SCIM organization exposed by a GitHub scope",
        icon="building-circle-arrow-right",
        color="#3B82F6",
        properties=ScimOrganizationNodeProperties,
    )
)
class ScimOrganization(ScimScopeAsset):
    scim_base_url: str | None = None

    @property
    def as_node(self) -> ScimNode:
        """Build the SCIM organization node within its hosting GitHub scope."""
        return ScimNode(
            id=self.scim_org_id,
            kinds=[nk.SCIM_ORGANIZATION],
            properties=ScimOrganizationNodeProperties(
                name=self.scope_name,
                displayname=self.scope_name,
                environmentid=self.scope_node_id,
                scim_base_url=self.scim_base_url,
                scope_type="enterprise" if self.enterprise_node_id else "organization",
                enterprise=self.enterprise_slug,
                organization=self.org_login,
            ),
        )

    @property
    def edges(self):
        return []


@app.asset(description="Represents enterprise-scoped SCIM organization input data.")
class EnterpriseScimOrganization(ScimOrganization):
    """Enterprise-scoped SCIM organization input model.

    This remains a distinct asset class so the converter can map enterprise and
    organization SCIM tables independently while emitting the same graph kind.
    """


@app.asset(
    node=NodeDef(
        kind=nk.SCIM_USER,
        description="User provisioned through GitHub SCIM",
        icon="user-gear",
        color="#10B981",
        properties=ScimUserNodeProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SCIM_USER,
            end=nk.SCIM_GROUP,
            kind=ek.SCIM_MEMBER_OF,
            description="SCIM user is a member of group",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCIM_ORGANIZATION,
            end=nk.SCIM_USER,
            kind=ek.SCIM_CONTAINS,
            description="SCIM organization contains user",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCIM_USER,
            end=nk.EXTERNAL_IDENTITY,
            kind=ek.SCIM_PROVISIONED,
            description="SCIM user is provisioned as a GitHub external identity",
            traversable=True,
        ),
        EdgeDef(
            start=nk.OKTA_USER,
            end=nk.SCIM_USER,
            kind=ek.SCIM_PROVISIONED,
            description="Temporary GitHound-compatible IdP-to-SCIM user correlation",
            traversable=True,
        ),
    ],
)
class ScimUser(ScimScopeAsset):
    id: str
    external_id: str | None = Field(default=None, alias="externalId")
    user_name: str | None = Field(default=None, alias="userName")
    display_name: str | None = Field(default=None, alias="displayName")
    profile_url: str | None = Field(default=None, alias="profileUrl")
    name: Name | None = None
    emails: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    roles: list[dict[str, Any]] = Field(default_factory=list)
    active: bool | None = None
    meta: ScimMeta | None = None
    emit_legacy_correlation: bool = False

    @property
    def as_node(self) -> ScimNode:
        """Preserve user state, resource metadata, roles, and groups in the SCIM node."""
        display_name = self.display_name or self.user_name or self.id
        return ScimNode(
            id=self.id,
            kinds=[nk.SCIM_USER],
            properties=ScimUserNodeProperties(
                name=self.user_name or self.id,
                displayname=display_name,
                environmentid=self.scope_node_id,
                external_id=self.external_id,
                user_name=self.user_name,
                enabled=self.active,
                active=self.active,
                given_name=self.name.given_name if self.name else None,
                family_name=self.name.family_name if self.name else None,
                mail=_primary_email(self.emails),
                profile_url=self.profile_url,
                resource_url=self.meta.location if self.meta else None,
                created_at=self.meta.created if self.meta else None,
                updated_at=self.meta.last_modified if self.meta else None,
                roles=json.dumps(self.roles),
                groups=json.dumps(self.groups),
                enterprise=self.enterprise_slug,
                organization=self.org_login,
            ),
        )

    @property
    def edges(self):
        """Yield containment for every user and access paths only for active users."""
        yield Edge(
            kind=ek.SCIM_CONTAINS,
            start=EdgePath(value=self.scim_org_id, match_by="id"),
            end=EdgePath(value=self.id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
        # Retain collected evidence and containment for every user, but emit
        # membership and provisioning paths only for explicitly active users.
        if self.active is not True:
            return
        seen_group_ids: set[str] = set()
        for group in self.groups:
            group_id = group.get("value")
            if not group_id:
                continue
            group_id = str(group_id)
            if group_id in seen_group_ids:
                continue
            seen_group_ids.add(group_id)
            # Group-side mapping already emits this edge when members contain
            # the user. Keep user-only evidence without duplicating that edge.
            if self._lookup.scim_group_has_member(
                self.scope_node_id, group_id, self.id
            ):
                continue
            yield Edge(
                kind=ek.SCIM_MEMBER_OF,
                start=EdgePath(value=self.id, match_by="id"),
                end=EdgePath(value=group_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )
        external_identity_id = self._lookup.external_identity_id_for_guid(
            self.id, self.scope_node_id
        )
        if external_identity_id:
            yield Edge(
                kind=ek.SCIM_PROVISIONED,
                start=EdgePath(value=self.id, match_by="id"),
                end=EdgePath(value=external_identity_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )
        if self.emit_legacy_correlation and self.external_id:
            yield Edge(
                kind=ek.SCIM_PROVISIONED,
                start=EdgePath(value=self.external_id, match_by="id"),
                end=EdgePath(value=self.id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )


@app.asset(description="Represents enterprise-scoped SCIM user input data.")
class EnterpriseScimUser(ScimUser):
    """Enterprise-scoped SCIM user input model."""


@app.asset(
    node=NodeDef(
        kind=nk.SCIM_GROUP,
        description="Group provisioned through GitHub SCIM",
        icon="users-gear",
        color="#EF4444",
        properties=ScimGroupNodeProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.SCIM_ORGANIZATION,
            end=nk.SCIM_GROUP,
            kind=ek.SCIM_CONTAINS,
            description="SCIM organization contains group",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCIM_USER,
            end=nk.SCIM_GROUP,
            kind=ek.SCIM_MEMBER_OF,
            description="SCIM user is a member of group",
            traversable=True,
        ),
        EdgeDef(
            start="Okta_Group",
            end=nk.SCIM_GROUP,
            kind=ek.SCIM_PROVISIONED,
            description="Temporary GitHound-compatible IdP-to-SCIM group correlation",
            traversable=True,
        ),
    ],
)
class ScimGroup(ScimScopeAsset):
    id: str
    external_id: str | None = Field(default=None, alias="externalId")
    display_name: str = Field(alias="displayName")
    members: list[dict[str, Any]] | None = None
    meta: ScimMeta | None = None
    emit_legacy_correlation: bool = False

    @property
    def legacy_okta_tenant_domain(self) -> str | None:
        provider = self._lookup.enterprise_idp_for_scope(self.scope_node_id)
        if not provider:
            return None
        foreign_idp_type, tenant_domain = detect_foreign_idp(*provider)
        return tenant_domain if foreign_idp_type == "okta" else None

    @property
    def as_node(self) -> ScimNode:
        """Build the group node with metadata and the returned member count."""
        return ScimNode(
            id=self.id,
            kinds=[nk.SCIM_GROUP],
            properties=ScimGroupNodeProperties(
                name=self.display_name,
                displayname=self.display_name,
                environmentid=self.scope_node_id,
                external_id=self.external_id,
                resource_url=self.meta.location if self.meta else None,
                created_at=self.meta.created if self.meta else None,
                updated_at=self.meta.last_modified if self.meta else None,
                member_count=len(self.members) if self.members is not None else None,
                enterprise=self.enterprise_slug,
                organization=self.org_login,
            ),
        )

    @property
    def edges(self):
        """Yield group containment, returned memberships, and optional legacy correlation."""
        yield Edge(
            kind=ek.SCIM_CONTAINS,
            start=EdgePath(value=self.scim_org_id, match_by="id"),
            end=EdgePath(value=self.id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
        for member in self.members or []:
            member_id = member.get("value")
            if member_id:
                yield Edge(
                    kind=ek.SCIM_MEMBER_OF,
                    start=EdgePath(value=str(member_id), match_by="id"),
                    end=EdgePath(value=self.id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )
        if self.emit_legacy_correlation and self.external_id:
            tenant_domain = self.legacy_okta_tenant_domain
            if tenant_domain:
                yield Edge(
                    kind=ek.SCIM_PROVISIONED,
                    start=ConditionalEdgePath(
                        kind="Okta_Group",
                        property_matchers=[
                            PropertyMatch(key="tenant_domain", value=tenant_domain),
                            PropertyMatch(key="name", value=self.external_id.upper()),
                        ],
                    ),
                    end=EdgePath(value=self.id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )
            else:
                self._lookup.warn_missing_legacy_scim_okta_tenant_once(
                    self.scope_node_id,
                    self.scope_name,
                )


ScimResource = ScimUser
