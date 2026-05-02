from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


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
        target_type: The target type of the installation (e.g., `Organization`).
        permissions: JSON string of the permissions granted to the app (e.g., `{"contents": "read", "metadata": "read"}`).
        events: JSON string of the webhook events the app subscribes to.
        created_at: When the app was installed.
        updated_at: When the installation was last updated.
        suspended_at: When the installation was suspended, if applicable.
        environment_name: The name of the environment (GitHub organization) where the app is installed.
        query_repositories: OpenGraph query for related repositories.
        query_app: OpenGraph query for related app.
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
    permissions: str | None = None
    events: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    suspended_at: datetime | None = None
    environment_name: str | None = None
    query_repositories: str | None = None
    query_app: str | None = None


class Account(BaseModel):
    login: str
    id: int
    node_id: str
    type: str


@app.asset(
    node=NodeDef(
        kind=nk.APP_INSTALLATION,
        description="GitHub App Installation",
        icon="plug",
        properties=GHAppInstallationProperties,
    ),
    edges=[
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
    repository_selection: str
    access_token_url: str | None = None
    app_id: int
    target_type: str
    permissions: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    org_node_id: str | None = None
    org_login: str | None = None
    single_file_name: str | None = None
    app_slug: str | None = None
    account: Account | None = None
    events: list[str] | None = None

    html_url: str | None = None
    repositories_url: str | None = None
    suspended_at: datetime | None = None
    description: str | None = None
    access_tokens_url: str | None = None

    @property
    def node_id(self):
        return f"GH_AppInstallation_{self.id}"

    @property
    def as_node(self) -> GHNode:
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
                permissions=self.permissions
                if isinstance(self.permissions, str)
                else None,
                events=self.events if isinstance(self.events, str) else None,
                created_at=self.created_at,
                updated_at=self.updated_at,
                suspended_at=self.suspended_at,
                environment_name=self.org_login or self._lookup.org_login(),
                environmentid=self.org_node_id or self._lookup.org_id(),
                query_repositories=f"MATCH p=(:GH_AppInstallation {{node_id:'{self.node_id}'}})-[:GH_CanAccess]->(:GH_Repository) RETURN p LIMIT 1000",
                query_app=f"MATCH p=(:GH_App)-[:GH_InstalledAs]->(:GH_AppInstallation {{node_id:'{self.node_id}'}}) RETURN p",
            ),
        )

    @property
    def _app_edges(self):
        if self.app_slug:
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
        if self.repository_selection == "all":
            org_node_id = self.org_node_id or self._lookup.org_id()
            for (repo_node_id,) in self._lookup.repository_node_ids(org_node_id):
                yield Edge(
                    kind=ek.CAN_ACCESS,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=repo_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(
                value=self.org_node_id or self._lookup.org_id(), match_by="id"
            ),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

        yield from self._app_edges
        yield from self._can_access_edges


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
        events: JSON string of the default webhook events the app subscribes to.
        installations_count: The total number of installations of this app across all organizations.
        created_at: When the app was created.
        updated_at: When the app was last updated.
        query_installations: OpenGraph query for related installations.
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
    events: list[str] | None = None
    installations_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    query_installations: str | None = None


class Owner(BaseModel):
    login: str
    id: int
    node_id: str
    type: str


@app.asset(
    node=NodeDef(
        kind=nk.APP,
        description="GitHub App Definition",
        icon="cube",
        properties=GHAppProperties,
    ),
)
class App(BaseAsset):
    """One record from `apps` → one GH_App node. Edges (GH_InstalledAs) are emitted by AppInstallationAsset."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int | None = None
    slug: str
    client_id: str | None = None
    node_id: str
    owner: Owner
    name: str
    description: str | None = None
    permissions: dict
    events: list[str]
    external_url: str | None = None
    html_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def as_node(self):
        aid = self.node_id
        return GHNode(
            kinds=[nk.APP],
            properties=GHAppProperties(
                name=self.name,
                displayname=self.name,
                node_id=aid,
                environmentid=self.org_node_id or self._lookup.org_id(),
                client_id=self.client_id,
                slug=self.slug,
                description=self.description,
                external_url=self.external_url,
                html_url=self.html_url,
                # owner_login=self.owner_login,
                # owner_node_id=self.owner_node_id,
                # owner_type=self.owner_type,
                # permissions=self.permissions,
                events=self.events,
                # installations_count=self.installations_count,
                created_at=self.created_at,
                updated_at=self.updated_at,
                query_installations=f"MATCH p=(:GH_App {{node_id:'{aid}'}})-[:GH_InstalledAs]->(:GH_AppInstallation) RETURN p",
            ),
        )

    @property
    def edges(self) -> list[Edge]:
        return []


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
    repo_node_id: str

    @property
    def as_node(self):
        return None

    @property
    def edges(self) -> list[Edge]:
        return [
            Edge(
                kind=ek.CAN_ACCESS,
                start=EdgePath(value=self.installation_node_id, match_by="id"),
                end=EdgePath(value=self.repo_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
        ]
