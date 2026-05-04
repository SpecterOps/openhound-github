from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
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


def enterprise_team_node_id(enterprise_id: str, team_id: str | int) -> str:
    return f"GH_EnterpriseTeam_{enterprise_id}_{team_id}"


def enterprise_role_node_id(enterprise_id: str, role_id: str | int) -> str:
    return f"GH_EnterpriseRole_{enterprise_id}_{role_id}"


@dataclass
class GHEnterpriseProperties(GHNodeProperties):
    """Properties for a GitHub enterprise.

    Attributes:
        collected: Whether this node was collected directly.
        slug: The enterprise slug.
        enterprise_name: The enterprise display name.
        description: The enterprise description.
        location: The enterprise location.
        url: The enterprise GitHub URL.
        website_url: The enterprise website URL.
        created_at: When the enterprise was created.
        updated_at: When the enterprise was last updated.
        billing_email: The enterprise billing email.
        security_contact_email: The enterprise security contact email.
        viewer_is_admin: Whether the authenticated viewer is an enterprise admin.
        environment_name: The enterprise environment name.
        query_organizations: Query for contained organizations.
    """

    collected: bool = True
    slug: str | None = None
    enterprise_name: str | None = None
    description: str | None = None
    location: str | None = None
    url: str | None = None
    website_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    billing_email: str | None = None
    security_contact_email: str | None = None
    viewer_is_admin: bool | None = None
    environment_name: str | None = None
    query_organizations: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE,
        description="GitHub Enterprise",
        icon="globe",
        properties=GHEnterpriseProperties,
    ),
)
class Enterprise(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    name: str | None = None
    slug: str
    description: str | None = None
    location: str | None = None
    url: str | None = None
    website_url: str | None = Field(alias="websiteUrl", default=None)
    created_at: str | None = Field(alias="createdAt", default=None)
    updated_at: str | None = Field(alias="updatedAt", default=None)
    billing_email: str | None = Field(alias="billingEmail", default=None)
    security_contact_email: str | None = Field(
        alias="securityContactEmail", default=None
    )
    viewer_is_admin: bool | None = Field(alias="viewerIsAdmin", default=None)
    organizations: dict | None = Field(default_factory=dict)

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE],
            properties=GHEnterpriseProperties(
                name=self.slug,
                displayname=self.name or self.slug,
                node_id=self.node_id,
                environmentid=self.node_id,
                environment_name=self.slug,
                slug=self.slug,
                enterprise_name=self.name,
                description=self.description,
                location=self.location,
                url=self.url,
                website_url=self.website_url,
                created_at=self.created_at,
                updated_at=self.updated_at,
                billing_email=self.billing_email,
                security_contact_email=self.security_contact_email,
                viewer_is_admin=self.viewer_is_admin,
                query_organizations=f"MATCH p=(:GH_Enterprise {{node_id:'{self.node_id}'}})-[:GH_Contains]->(:GH_Organization) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []


@dataclass
class GHEnterpriseOrganizationProperties(GHNodeProperties):
    """Properties for an enterprise-discovered organization stub.

    Attributes:
        collected: Whether this organization was collected in full.
        login: The organization login.
        environment_name: The organization environment name.
        query_enterprise: Query for the containing enterprise.
    """

    collected: bool = False
    login: str | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORGANIZATION,
        description="GitHub Organization discovered from an enterprise",
        icon="building",
        properties=GHEnterpriseOrganizationProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ORGANIZATION,
            kind=ek.CONTAINS,
            description="Enterprise contains organization",
            traversable=False,
        ),
    ],
)
class EnterpriseOrganization(BaseAsset):
    id: str
    login: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ORGANIZATION],
            properties=GHEnterpriseOrganizationProperties(
                name=self.login,
                displayname=self.login,
                node_id=self.node_id,
                environmentid=self.node_id,
                environment_name=self.login,
                login=self.login,
                collected=False,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_Organization {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


class EmbeddedUser(BaseModel):
    id: str
    database_id: int = Field(alias="databaseId")
    login: str
    name: str | None = None
    email: str
    company: str | None = None


class BaseUser(BaseModel):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    typename: str = Field(alias="__typename")
    id: str
    login: str
    name: str | None = None
    url: str | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    user: EmbeddedUser | None = None


@dataclass
class GHEnterpriseUserProperties(GHNodeProperties):
    """Properties for a GitHub enterprise member user.

    Attributes:
        collected: Whether this user was collected directly.
        login: The GitHub login.
        full_name: The user's display name.
        company: The user's company.
        email: The user's public email.
        environment_name: The enterprise environment name.
        query_enterprises: Query for enterprise memberships.
    """

    collected: bool = True
    login: str | None = None
    full_name: str | None = None
    company: str | None = None
    email: str | None = None
    environment_name: str | None = None
    query_enterprises: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.USER,
        description="GitHub enterprise member user",
        icon="user",
        properties=GHEnterpriseUserProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.USER,
            kind=ek.HAS_MEMBER,
            description="Enterprise has user member",
            traversable=False,
        ),
    ],
)
class EnterpriseUser(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    login: str
    name: str | None = None
    email: str | None = None
    company: str | None = None
    enterprise_node_id: str | None = None
    enterprise_slug: str
    has_direct_enterprise_membership: bool = True

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.USER],
            properties=GHEnterpriseUserProperties(
                name=self.login,
                displayname=self.name or self.login,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                login=self.login,
                full_name=self.name,
                company=self.company,
                email=self.email,
                query_enterprises=f"MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_User {{node_id:'{self.node_id}'}}) RETURN p UNION MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_EnterpriseManagedUser)-[:GH_MapsToUser]->(:GH_User {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        if self.has_direct_enterprise_membership:
            yield Edge(
                kind=ek.HAS_MEMBER,
                start=EdgePath(value=self.enterprise_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )


@dataclass
class GHEnterpriseManagedUserProperties(GHNodeProperties):
    """Properties for a GitHub enterprise managed user wrapper.

    Attributes:
        login: The managed user login.
        full_name: The managed user display name.
        url: The managed user URL.
        created_at: When the managed user was created.
        updated_at: When the managed user was last updated.
        github_user_id: The backing GitHub user ID.
        github_username: The backing GitHub username.
        environment_name: The enterprise environment name.
        query_enterprises: Query for enterprises containing this managed user.
        query_mapped_user: Query for the backing GitHub user.
    """

    login: str | None = None
    full_name: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    github_user_id: str | None = None
    github_username: str | None = None
    environment_name: str | None = None
    query_enterprises: str | None = None
    query_mapped_user: str | None = None


class EnterpriseManagedBackingUser(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    database_id: int | None = Field(alias="databaseId", default=None)
    login: str
    name: str | None = None
    email: str | None = None
    company: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_MANAGED_USER,
        description="GitHub enterprise managed user",
        icon="user-lock",
        properties=GHEnterpriseManagedUserProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_MANAGED_USER,
            kind=ek.HAS_MEMBER,
            description="Enterprise has enterprise managed user member",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_MANAGED_USER,
            end=nk.USER,
            kind=ek.MAPS_TO_USER,
            description="Enterprise managed user maps to GitHub user",
            traversable=False,
        ),
    ],
)
class EnterpriseManagedUser(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    login: str
    name: str | None = None
    url: str | None = None
    created_at: datetime | None = Field(alias="createdAt")
    updated_at: datetime | None = Field(alias="updatedAt")
    user: EnterpriseManagedBackingUser | None = None
    enterprise_node_id: str | None = None
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return self.id

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_MANAGED_USER],
            properties=GHEnterpriseManagedUserProperties(
                name=self.login,
                displayname=self.name or self.login,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                login=self.login,
                full_name=self.name,
                url=self.url,
                created_at=self.created_at,
                updated_at=self.updated_at,
                github_user_id=self.user.id if self.user else None,
                github_username=self.user.login if self.user else None,
                query_enterprises=f"MATCH p=(:GH_Enterprise)-[:GH_HasMember]->(:GH_EnterpriseManagedUser {{node_id:'{self.node_id}'}}) RETURN p",
                query_mapped_user=f"MATCH p=(:GH_EnterpriseManagedUser {{node_id:'{self.node_id}'}})-[:GH_MapsToUser]->(:GH_User) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_MEMBER,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
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


@dataclass
class GHEnterpriseTeamProperties(GHNodeProperties):
    """Properties for a GitHub enterprise team.

    Attributes:
        github_team_id: The raw GitHub enterprise team ID.
        slug: The enterprise team slug.
        projected_slug: The organization-projected team slug.
        group_id: The linked SCIM group ID.
        description: The team description.
        created_at: When the team was created.
        updated_at: When the team was last updated.
        environment_name: The enterprise environment name.
        query_enterprise: Query for the containing enterprise.
        query_assigned_organizations: Query for assigned organizations.
        query_projected_teams: Query for projected organization teams.
        query_members: Query for team members.
    """

    github_team_id: str | int | None = None
    slug: str | None = None
    projected_slug: str | None = None
    group_id: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None
    query_assigned_organizations: str | None = None
    query_projected_teams: str | None = None
    query_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_TEAM,
        description="GitHub Enterprise Team",
        icon="users-between-lines",
        properties=GHEnterpriseTeamProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_TEAM,
            kind=ek.CONTAINS,
            description="Enterprise contains team",
            traversable=False,
        ),
    ],
)
class EnterpriseTeam(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    name: str
    slug: str
    group_id: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_TEAM],
            properties=GHEnterpriseTeamProperties(
                name=self.name,
                displayname=self.name,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                github_team_id=self.id,
                slug=self.slug,
                projected_slug=self.slug,
                group_id=self.group_id,
                description=self.description,
                created_at=self.created_at,
                updated_at=self.updated_at,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}}) RETURN p",
                query_assigned_organizations=f"MATCH p=(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}})-[:GH_AssignedTo]->(:GH_Organization) RETURN p",
                query_projected_teams=f"MATCH p=(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}})-[:GH_MemberOf]->(:GH_Team) RETURN p",
                query_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole)-[:GH_MemberOf]->(:GH_EnterpriseTeam {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


@dataclass
class GHEnterpriseTeamRoleProperties(GHNodeProperties):
    """Properties for an enterprise team role.

    Attributes:
        enterpriseid: The containing enterprise node ID.
        team_name: The team display name.
        team_id: The enterprise team node ID.
        short_name: The role short name.
        type: The role type.
        environment_name: The enterprise environment name.
        query_team: Query for the team.
        query_members: Query for role members.
    """

    enterpriseid: str | None = None
    team_name: str | None = None
    team_id: str | None = None
    short_name: str | None = None
    type: str | None = None
    environment_name: str | None = None
    query_team: str | None = None
    query_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.TEAM_ROLE,
        description="GitHub Enterprise Team Role",
        icon="user-tie",
        properties=GHEnterpriseTeamRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.TEAM_ROLE,
            end=nk.ENTERPRISE_TEAM,
            kind=ek.MEMBER_OF,
            description="Enterprise team role belongs to enterprise team",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamRole(BaseAsset):
    id: int
    name: str
    slug: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def enterprise_team_node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.id)

    @property
    def node_id(self) -> str:
        return f"{self.enterprise_team_node_id}_members"

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.TEAM_ROLE, "GH_Role"],
            properties=GHEnterpriseTeamRoleProperties(
                name=f"{self.enterprise_slug}/{self.slug}/members",
                displayname="members",
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                enterpriseid=self.enterprise_node_id,
                team_name=self.name,
                team_id=self.enterprise_team_node_id,
                short_name="members",
                type="team",
                query_team=f"MATCH p=(:GH_TeamRole {{node_id:'{self.node_id}'}})-[:GH_MemberOf]->(:GH_EnterpriseTeam {{node_id:'{self.enterprise_team_node_id}'}}) RETURN p",
                query_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.MEMBER_OF,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.TEAM_ROLE,
            kind=ek.HAS_ROLE,
            description="User has enterprise team role",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamMember(BaseAsset):
    node_id: str
    login: str | None = None
    team_id: int
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def role_node_id(self) -> str:
        return (
            f"{enterprise_team_node_id(self.enterprise_node_id, self.team_id)}_members"
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=self.role_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.ORGANIZATION,
            kind=ek.ASSIGNED_TO,
            description="Enterprise team is assigned to organization",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.TEAM,
            kind=ek.MEMBER_OF,
            description="Enterprise team maps to projected organization team",
            traversable=True,
        ),
    ],
)
class EnterpriseTeamOrganization(BaseAsset):
    node_id: str
    login: str | None = None
    team_id: int
    projected_slug: str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def enterprise_team_node_id(self) -> str:
        return enterprise_team_node_id(self.enterprise_node_id, self.team_id)

    @property
    def edges(self):
        yield Edge(
            kind=ek.ASSIGNED_TO,
            start=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        yield Edge(
            kind=ek.MEMBER_OF,
            start=EdgePath(value=self.enterprise_team_node_id, match_by="id"),
            end=ConditionalEdgePath(
                kind=nk.TEAM,
                property_matchers=[
                    PropertyMatch(key="environmentid", value=self.node_id),
                    PropertyMatch(key="slug", value=self.projected_slug),
                ],
            ),
            properties=EdgeProperties(traversable=True),
        )


@dataclass
class GHEnterpriseRoleProperties(GHNodeProperties):
    """Properties for a GitHub enterprise role.

    Attributes:
        github_role_id: The raw GitHub role ID.
        short_name: The role short name.
        description: The role description.
        source: The role source.
        type: The role type.
        created_at: When the role was created.
        updated_at: When the role was last updated.
        permissions: Raw enterprise permission strings.
        environment_name: The enterprise environment name.
        query_enterprise: Query for the containing enterprise.
        query_explicit_members: Query for direct user members.
        query_team_members: Query for team-assigned members.
    """

    github_role_id: str | int | None = None
    short_name: str | None = None
    description: str | None = None
    source: str | None = None
    type: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    permissions: list[str] | None = None
    environment_name: str | None = None
    query_enterprise: str | None = None
    query_explicit_members: str | None = None
    query_team_members: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_ROLE,
        description="GitHub Enterprise Role",
        icon="user-tie",
        properties=GHEnterpriseRoleProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.CONTAINS,
            description="Enterprise contains role",
            traversable=False,
        ),
    ],
)
class EnterpriseRole(BaseAsset):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int | str
    name: str
    description: str | None = None
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    permissions: list[str] = Field(default_factory=list)
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return enterprise_role_node_id(self.enterprise_node_id, self.id)

    @property
    def role_type(self) -> str:
        return "default" if self.source in {"Predefined", "Default"} else "custom"

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENTERPRISE_ROLE, "GH_Role"],
            properties=GHEnterpriseRoleProperties(
                name=f"{self.enterprise_slug}/{self.name}",
                displayname=self.name,
                node_id=self.node_id,
                environmentid=self.enterprise_node_id,
                environment_name=self.enterprise_slug,
                github_role_id=self.id,
                short_name=self.name,
                description=self.description,
                source=self.source,
                type=self.role_type,
                created_at=self.created_at,
                updated_at=self.updated_at,
                permissions=self.permissions,
                query_enterprise=f"MATCH p=(:GH_Enterprise {{node_id:'{self.enterprise_node_id}'}})-[:GH_Contains]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_explicit_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
                query_team_members=f"MATCH p=(:GH_User)-[:GH_HasRole]->(:GH_TeamRole)-[:GH_MemberOf]->(:GH_EnterpriseTeam)-[:GH_HasRole]->(:GH_EnterpriseRole {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.HAS_ROLE,
            description="User has enterprise role",
            traversable=True,
        ),
    ],
)
class EnterpriseRoleUser(BaseAsset):
    node_id: str
    login: str | None = None
    assignment: str | None = None
    role_id: int | str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def role_node_id(self) -> str:
        return enterprise_role_node_id(self.enterprise_node_id, self.role_id)

    @property
    def edges(self):
        if self.assignment == "direct" and self.node_id:
            yield Edge(
                kind=ek.HAS_ROLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.role_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_TEAM,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.HAS_ROLE,
            description="Enterprise team has enterprise role",
            traversable=True,
        ),
    ],
)
class EnterpriseRoleTeam(BaseAsset):
    id: int
    role_id: int | str
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self) -> None:
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_ROLE,
            start=EdgePath(
                value=enterprise_team_node_id(self.enterprise_node_id, self.id),
                match_by="id",
            ),
            end=EdgePath(
                value=enterprise_role_node_id(self.enterprise_node_id, self.role_id),
                match_by="id",
            ),
            properties=EdgeProperties(traversable=True),
        )


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
                environmentid=self.enterprise_node_id,
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
            start=EdgePath(value=self.enterprise_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


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
                environmentid=self.enterprise_node_id,
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
