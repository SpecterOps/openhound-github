from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, Field, model_validator

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.app_permissions import split_app_permissions
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
    REPOSITORY_SCOPE_TYPE,
    UNRESTRICTED_BRANCH_CREATION_SCOPE,
    scope_node_id,
)


@dataclass
class GHAppInstallationProperties(GHNodeProperties):
    """App installation properties and accordion panel queries.

    Attributes:
        id: The GitHub installation ID.
        app_id: The GitHub App's numeric ID (shared across all installations of the same app).
        app_slug: The app's URL-friendly slug identifier.
        description: The app's description.
        html_url: URL to the app's GitHub page.
        access_tokens_url: API URL to create installation access tokens.
        repositories_url: API URL to list repositories accessible to this installation.
        repository_selection: Whether the app has access to `all` repositories or `selected` repositories.
        target_type: The target type of the installation (`Organization` or `Enterprise`).
        permissions_repository: Granted repository permissions as `permission:access` values.
        permissions_organization: Granted organization permissions as `permission:access` values.
        permissions_enterprise: Granted enterprise permissions as `permission:access` values.
        permissions_account: Granted account permissions as `permission:access` values.
        permissions_unclassified: Granted unclassified permissions as `permission:access` values.
        events: Webhook events the app subscribes to.
        created_at: When the app was installed.
        updated_at: When the installation was last updated.
        suspended_at: When the installation was suspended, if applicable.
        environment_name: The organization or enterprise where the app is installed.
        environment_slug: The organization login or enterprise slug of the installation target.
    """

    id: int | None = None
    app_id: int | None = None
    app_slug: str | None = None
    description: str | None = None
    html_url: str | None = None
    access_tokens_url: str | None = None
    repositories_url: str | None = None
    repository_selection: str | None = None
    target_type: str | None = None
    permissions_repository: list[str] | None = None
    permissions_organization: list[str] | None = None
    permissions_enterprise: list[str] | None = None
    permissions_account: list[str] | None = None
    permissions_unclassified: list[str] | None = None
    events: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    suspended_at: datetime | None = None
    environment_name: str | None = None
    environment_slug: str | None = None


class Account(BaseModel):
    login: str | None = None
    id: int
    node_id: str | None = None
    type: str | None = None
    slug: str | None = None
    name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.APP_INSTALLATION,
        description="GitHub App Installation",
        icon="plug",
        properties=GHAppInstallationProperties,
    ),
    edges=[
        *[
            EdgeDef(
                start=nk.APP_INSTALLATION,
                end=target,
                kind=ek.CAN_CREATE_BRANCH,
                description="App installation can create freely named branches in repository or scope",
                traversable=True,
            )
            for target in (nk.REPOSITORY, nk.SCOPE)
        ],
        *[
            EdgeDef(
                start=nk.APP_INSTALLATION,
                end=target,
                kind=ek.CAN_ACCESS,
                description="App installation can access its installation target",
                traversable=False,
            )
            for target in (nk.ORGANIZATION, nk.ENTERPRISE)
        ],
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.APP_INSTALLATION,
            kind=ek.CONTAINS,
            description="Enterprise contains app installation",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.APP_INSTALLATION,
            kind=ek.CONTAINS,
            description="Org contains app installation",
            traversable=False,
        ),
        EdgeDef(
            start=nk.APP,
            end=nk.APP_INSTALLATION,
            kind=ek.INSTALLED_AS,
            description="App is installed as this installation",
            traversable=True,
        ),
    ],
)
class AppInstallation(BaseAsset):
    """One record from `app_installations` → one GH_AppInstallation node + GH_Contains and GH_InstalledAs edges."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    repository_selection: str | None = None
    access_token_url: str | None = None
    app_id: int
    target_type: str
    permissions: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    single_file_name: str | None = None
    app_slug: str | None = None
    account: Account | None = None
    events: list[str] | None = None

    html_url: str | None = None
    repositories_url: str | None = None
    suspended_at: datetime | None = None
    description: str | None = None
    access_tokens_url: str | None = None

    # Additional
    org_login: str | None = None
    environment_slug: str | None = None
    enterprise_name: str | None = None
    enterprise_node_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_environment_context(cls, data):
        """Read canonical context while accepting legacy collection fields."""
        if isinstance(data, dict):
            data = dict(data)
            if not data.get("environment_slug"):
                data["environment_slug"] = (
                    data.get("enterprise_name")
                    if data.get("target_type") == "Enterprise"
                    else data.get("org_login")
                )
        return data

    @property
    def node_id(self):
        return f"GH_AppInstallation_{self.id}"

    @property
    def org_node_id(self) -> str | None:
        """Resolve the containing organization for organization installations only."""
        if self.target_type != "Organization" or not self.environment_slug:
            return None
        return self._lookup.org_id_for_login(self.environment_slug)

    @property
    def environment_node_id(self) -> str | None:
        """Resolve the installation target to its enterprise or organization node."""
        if self.target_type == "Enterprise":
            return self.enterprise_node_id
        return self.org_node_id

    @property
    def as_node(self) -> GHNode:
        """Build the installation node with granted permissions and target context."""
        slug = self.app_slug or str(self.app_id)
        return GHNode(
            kinds=["GH_AppInstallation"],
            properties=GHAppInstallationProperties(
                name=slug,
                displayname=slug,
                node_id=self.node_id,
                id=self.id,
                app_id=self.app_id,
                app_slug=slug,
                description=self.description,
                html_url=self.html_url,
                access_tokens_url=self.access_tokens_url,
                repositories_url=self.repositories_url,
                repository_selection=self.repository_selection,
                target_type=self.target_type,
                **split_app_permissions(self.permissions),
                events=self.events,
                created_at=self.created_at,
                updated_at=self.updated_at,
                suspended_at=self.suspended_at,
                environment_name=self.environment_slug,
                environment_slug=self.environment_slug,
                environmentid=self.environment_node_id,
            ),
        )

    @property
    def _app_edges(self):
        """Link the registered app to this installation when its slug resolves."""
        if self.app_slug:
            # App slugs identify one registration across all installation targets.
            app_node_id = self._lookup.app_node_id(self.app_slug)
            if app_node_id:
                yield Edge(
                    kind=ek.INSTALLED_AS,
                    start=EdgePath(value=app_node_id, match_by="id"),
                    end=EdgePath(value=self.node_id, match_by="id"),
                    properties=EdgeProperties(traversable=True),
                )

    @property
    def _can_access_edges(self):
        """Link the installation target and any all-repository organization scope."""
        target_node_id = self.environment_node_id
        if not target_node_id:
            return
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=self.node_id, match_by="id"),
            end=EdgePath(value=target_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        if self.target_type == "Organization" and self.repository_selection == "all":
            yield Edge(
                kind=ek.CAN_ACCESS,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(
                    value=scope_node_id(
                        target_node_id,
                        REPOSITORY_SCOPE_TYPE,
                        ALL_REPOSITORIES_SCOPE,
                    ),
                    match_by="id",
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _branch_creation_access_query(self) -> str:
        return (
            f"MATCH p=(installation:GH_AppInstallation {{node_id:'{self.node_id}'}})"
            "-[:GH_CanAccess|GH_ScopedTo*1..2]->(repository:GH_Repository) "
            "WHERE 'contents:write' IN installation.permissions_repository "
            "AND installation.suspended_at IS NULL "
        )

    @property
    def _can_create_branch_edges(self):
        if (
            self.target_type != "Organization"
            or self.suspended_at is not None
            or self.permissions.get("contents") != "write"
            or self.repository_selection not in {"all", "selected"}
            or not self.environment_slug
            or not self.org_node_id
        ):
            return

        use_scope = self.repository_selection == "all" and (
            self._lookup.branch_creation_scope_available(
                self.environment_slug, self.org_node_id
            )
        )
        if use_scope and self._lookup.canonical_scope_has_targets(
            self.environment_slug,
            REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
            UNRESTRICTED_BRANCH_CREATION_SCOPE,
        ):
            target_scope_id = scope_node_id(
                self.org_node_id,
                REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
                UNRESTRICTED_BRANCH_CREATION_SCOPE,
            )
            yield Edge(
                kind=ek.CAN_CREATE_BRANCH,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(
                    value=target_scope_id,
                    match_by="id",
                ),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    reason="contents_write_and_all_repository_access",
                    query_composition=(
                        self._branch_creation_access_query
                        + f"MATCH p1=(:GH_Scope {{node_id:'{target_scope_id}'}})"
                        "-[:GH_ScopedTo]->(repository) RETURN p, p1"
                    ),
                ),
            )
        for (
            repository_id,
            reason,
        ) in self._lookup.app_installation_branch_creation_repositories(
            self.id, self.environment_slug, exclude_shared=use_scope
        ):
            query = (
                self._branch_creation_access_query
                + f"AND repository.node_id = '{repository_id}' "
            )
            if reason == "app_push_allowance":
                query += (
                    "MATCH p1=(installation)-[:GH_RestrictionsCanPush]->"
                    "(:GH_BranchProtectionRule)<-[:GH_Contains]-(repository) RETURN p, p1"
                )
            else:
                query += "RETURN p"
            yield Edge(
                kind=ek.CAN_CREATE_BRANCH,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=repository_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    reason=reason,
                    query_composition=query,
                ),
            )

    @property
    def edges(self):
        """Yield containment, parent app, and target/repository access scope."""
        if self.environment_node_id:
            yield Edge(
                kind=ek.CONTAINS,
                start=EdgePath(value=self.environment_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

        yield from self._app_edges
        yield from self._can_access_edges
        yield from self._can_create_branch_edges


@dataclass
class GHAppProperties(GHNodeProperties):
    """App definition properties and accordion panel queries.

    Attributes:
        id: The GitHub App's numeric ID.
        client_id: The app's OAuth client ID.
        slug: The app's URL-friendly slug identifier.
        description: The app's description.
        external_url: The app's external homepage URL.
        html_url: URL to the app's GitHub page.
        owner_login: The login of the user or organization that owns the app.
        owner_node_id: The node_id of the user or organization that owns the app.
        owner_type: The type of the owner (e.g., `User`, `Organization`).
        registration_origin: Ownership classification: tenant_owned, member_owned,
            third_party (no internal ownership evidence), or unknown.
        permissions_repository: Requested repository permissions as `permission:access` values.
        permissions_organization: Requested organization permissions as `permission:access` values.
        permissions_enterprise: Requested enterprise permissions as `permission:access` values.
        permissions_account: Requested account permissions as `permission:access` values.
        permissions_unclassified: Requested unclassified permissions as `permission:access` values.
        environment_slug: The organization login or enterprise slug where the app was collected.
        events: Default webhook events the app subscribes to.
        installations_count: The total number of installations of this app across all organizations.
        created_at: When the app was created.
        updated_at: When the app was last updated.
    """

    id: int | None = None
    client_id: str | None = None
    slug: str | None = None
    description: str | None = None
    external_url: str | None = None
    html_url: str | None = None
    owner_login: str | None = None
    owner_node_id: str | None = None
    owner_type: str | None = None
    registration_origin: str | None = None
    permissions_repository: list[str] | None = None
    permissions_organization: list[str] | None = None
    permissions_enterprise: list[str] | None = None
    permissions_account: list[str] | None = None
    permissions_unclassified: list[str] | None = None
    environment_slug: str | None = None
    events: list[str] | None = None
    installations_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Owner(BaseModel):
    login: str
    id: int
    node_id: str
    type: str
    name: str | None = None
    description: str | None = None
    company: str | None = None
    html_url: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.APP,
        description="GitHub App Definition",
        icon="cube",
        properties=GHAppProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.APP,
            kind=ek.OWNS,
            description="Enterprise owns GitHub App",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.APP,
            kind=ek.OWNS,
            description="Organization owns GitHub App",
            traversable=True,
        ),
        EdgeDef(
            start=nk.USER,
            end=nk.APP,
            kind=ek.OWNS,
            description="User owns GitHub App",
            traversable=True,
        ),
    ],
)
class App(BaseAsset):
    """One record from `apps` → one GH_App node. Edges (GH_InstalledAs) are emitted by AppInstallationAsset."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int | None = None
    slug: str
    client_id: str | None = None
    node_id: str
    owner: Owner | None = None
    name: str
    description: str | None = None
    permissions: dict
    events: list[str]
    external_url: str | None = None
    html_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Additional
    org_login: str | None = None
    environment_slug: str | None = None
    enterprise_node_id: str | None = None
    collected_org_node_id: str | None = Field(default=None, alias="org_node_id")

    @model_validator(mode="before")
    @classmethod
    def normalize_environment_context(cls, data):
        """Read canonical context while accepting legacy collection fields."""
        if isinstance(data, dict) and not data.get("environment_slug"):
            data = {**data, "environment_slug": data.get("org_login")}
        return data

    @property
    def org_node_id(self) -> str | None:
        """Resolve organization collection context, excluding enterprise context."""
        if self.collected_org_node_id:
            return self.collected_org_node_id
        if self.enterprise_node_id or not self.environment_slug:
            return None
        return self._lookup.org_id_for_login(self.environment_slug)

    @property
    def registration_origin(self) -> str:
        """Classify app ownership relative to the collected tenant when known."""
        if self.owner is None:
            return "unknown"

        owner_type = self.owner.type.casefold()
        if owner_type == "user":
            return (
                "member_owned"
                if self._lookup.is_collected_user_node_id(self.owner.node_id)
                else "third_party"
            )

        if owner_type == "organization":
            if self._lookup.is_tenant_organization_node_id(self.owner.node_id):
                return "tenant_owned"
            return "third_party"

        if owner_type == "enterprise":
            enterprise_id = self._lookup.enterprise_id()
            return (
                "tenant_owned" if self.owner.node_id == enterprise_id else "third_party"
            )

        return "unknown"

    @property
    def registration_owner_node_id(self) -> str | None:
        if self.owner is None:
            return None

        owner_type = self.owner.type.casefold()
        if owner_type == "organization":
            owner_exists = self._lookup.is_tenant_organization_node_id(
                self.owner.node_id
            )
        elif owner_type == "enterprise":
            owner_exists = self._lookup.enterprise_id() == self.owner.node_id
        elif owner_type == "user":
            owner_exists = self._lookup.is_collected_user_node_id(self.owner.node_id)
        else:
            owner_exists = False

        owner_exists = owner_exists or (
            owner_type in {"user", "organization", "enterprise"}
            and self._lookup.has_app_owner(self.owner.node_id, self.owner.type)
        )
        return self.owner.node_id if owner_exists else None

    @property
    def as_node(self):
        """Build the app node with owner metadata and requested permissions."""
        aid = self.node_id
        return GHNode(
            kinds=[nk.APP],
            properties=GHAppProperties(
                name=self.name,
                displayname=self.name,
                node_id=aid,
                environmentid=self.enterprise_node_id or self.org_node_id,
                environment_slug=self.environment_slug,
                id=self.id,
                client_id=self.client_id,
                slug=self.slug,
                description=self.description,
                external_url=self.external_url,
                html_url=self.html_url,
                owner_login=self.owner.login if self.owner else None,
                owner_node_id=self.owner.node_id if self.owner else None,
                owner_type=self.owner.type if self.owner else None,
                registration_origin=self.registration_origin,
                **split_app_permissions(self.permissions),
                # installations_count=self.installations_count,
                events=self.events,
                created_at=self.created_at,
                updated_at=self.updated_at,
            ),
        )

    @property
    def edges(self) -> list[Edge]:
        owner_node_id = self.registration_owner_node_id
        if owner_node_id is None:
            return []

        return [
            Edge(
                kind=ek.OWNS,
                start=EdgePath(value=owner_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )
        ]


@app.asset(
    edges=[
        EdgeDef(
            start=nk.APP_INSTALLATION,
            end=nk.REPOSITORY,
            kind=ek.CAN_ACCESS,
            description="App installation can access repository",
            traversable=False,
        )
    ],
)
class AppInstallationRepoAccess(BaseAsset):
    """One record from `app_installation_repo_access` → GH_CanAccess edge. No node."""

    installation_node_id: str
    repository_database_id: int
    repo_full_name: str | None = None
    org_login: str

    @property
    def as_node(self):
        return None

    @property
    def edges(self) -> list[Edge]:
        """Link the installation to a collected repository when it resolves."""
        repo_node_id = self._lookup.repository_node_id_for_database_id(
            self.repository_database_id, self.org_login
        )
        if not repo_node_id:
            return []
        return [
            Edge(
                kind=ek.CAN_ACCESS,
                start=EdgePath(value=self.installation_node_id, match_by="id"),
                end=EdgePath(value=repo_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
        ]
