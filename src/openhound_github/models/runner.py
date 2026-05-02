import json
from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHRunnerGroupProperties(GHNodeProperties):
    """GHRunnerGroupProperties properties.

    Attributes:
        group_id: The GitHub runner group ID.
        group_name: The runner group display name.
        visibility: Which repositories can use this group: `all`, `private`, or `selected`.
        default: Whether this is the default runner group.
        inherited: Whether this runner group is inherited.
        allows_public_repositories: Whether public repositories may use this group.
        restricted_to_workflows: Whether access is restricted to selected workflows.
        selected_workflows: JSON array of selected workflows, if configured.
        runners_url: API URL for runners in this group.
        environment_name: The name of the environment (GitHub organization).
        query_runners: OpenGraph query for related runners.
        query_repositories: OpenGraph query for related repositories.
    """

    group_id: int | None = None
    group_name: str | None = None
    visibility: str | None = None
    default: bool | None = None
    inherited: bool | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
    selected_workflows: str | None = None
    runners_url: str | None = None
    environment_name: str | None = None
    query_runners: str | None = None
    query_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.RUNNER_GROUP,
        description="GitHub self-hosted runner group",
        icon="server",
        properties=GHRunnerGroupProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.RUNNER_GROUP,
            kind=ek.CONTAINS,
            description="Organization contains runner group",
            traversable=False,
        ),
    ],
)
class RunnerGroup(BaseAsset):
    id: int
    name: str
    visibility: str | None = None
    default: bool | None = None
    inherited: bool | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
    selected_workflows: list[str] | None = None
    runners_url: str | None = None
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def _org_node_id(self) -> str:
        return self.org_node_id or self._lookup.org_id()

    @property
    def _org_login(self) -> str:
        return self.org_login or self._lookup.org_login()

    @property
    def node_id(self) -> str:
        return f"{self._org_node_id}_runner_group_{self.id}"

    @property
    def as_node(self) -> GHNode:
        gid = self.node_id
        return GHNode(
            kinds=[nk.RUNNER_GROUP],
            properties=GHRunnerGroupProperties(
                name=f"{self._org_login}/{self.name}",
                displayname=self.name,
                node_id=gid,
                group_id=self.id,
                group_name=self.name,
                visibility=self.visibility,
                default=self.default,
                inherited=self.inherited,
                allows_public_repositories=self.allows_public_repositories,
                restricted_to_workflows=self.restricted_to_workflows,
                selected_workflows=json.dumps(self.selected_workflows or []),
                runners_url=self.runners_url,
                environment_name=self._org_login,
                environmentid=self._org_node_id,
                query_runners=f"MATCH p=(:GH_RunnerGroup {{node_id:'{gid}'}})-[:GH_Contains]->(:GH_OrgRunner) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_OrgRunner)<-[:GH_Contains]-(:GH_RunnerGroup {{node_id:'{gid}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


@dataclass
class GHRunnerProperties(GHNodeProperties):
    """GHRunnerProperties properties.

    Attributes:
        scope: Whether the runner is organization or repository scoped.
        runner_id: The GitHub runner ID.
        os: The runner operating system.
        status: The runner status.
        busy: Whether the runner is currently busy.
        ephemeral: Whether the runner is ephemeral.
        labels: JSON array of runner labels.
        runner_group_id: The associated runner group ID.
        runner_group_name: The associated runner group name.
        runner_group_visibility: Runner group visibility when organization scoped.
        repository_name: The repository name for repository-scoped runners.
        repository_id: The repository node_id for repository-scoped runners.
        repository_full_name: The full repository name for repository-scoped runners.
        environment_name: The name of the environment (GitHub organization).
        query_group: OpenGraph query for related group.
        query_repositories: OpenGraph query for related repositories.
    """

    scope: str | None = None
    runner_id: int | None = None
    os: str | None = None
    status: str | None = None
    busy: bool | None = None
    ephemeral: bool | None = None
    labels: str | None = None
    runner_group_id: int | None = None
    runner_group_name: str | None = None
    runner_group_visibility: str | None = None
    repository_name: str | None = None
    repository_id: str | None = None
    repository_full_name: str | None = None
    environment_name: str | None = None
    query_group: str | None = None
    query_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORG_RUNNER,
        description="GitHub organization-scoped self-hosted runner",
        icon="microchip",
        properties=GHRunnerProperties,
    )
)
class OrgRunner(BaseAsset):
    id: int
    name: str
    os: str | None = None
    status: str | None = None
    busy: bool | None = None
    ephemeral: bool | None = None
    labels: list[dict] = Field(default_factory=list)
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def _org_node_id(self) -> str:
        return self.org_node_id or self._lookup.org_id()

    @property
    def _org_login(self) -> str:
        return self.org_login or self._lookup.org_login()

    @property
    def node_id(self) -> str:
        return f"{self._org_node_id}_org_runner_{self.id}"

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.ORG_RUNNER, nk.RUNNER],
            properties=GHRunnerProperties(
                name=self.name,
                displayname=self.name,
                node_id=rid,
                scope="organization",
                runner_id=self.id,
                os=self.os,
                status=self.status,
                busy=self.busy,
                ephemeral=self.ephemeral,
                labels=json.dumps(self.labels),
                environment_name=self._org_login,
                environmentid=self._org_node_id,
                query_group=f"MATCH p=(:GH_RunnerGroup)-[:GH_Contains]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []


@app.asset(
    edges=[
        EdgeDef(
            start=nk.RUNNER_GROUP,
            end=nk.ORG_RUNNER,
            kind=ek.CONTAINS,
            description="Runner group contains organization runner",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_RUNNER,
            kind=ek.CAN_USE_RUNNER,
            description="Repository can dispatch jobs to runner",
            traversable=False,
        ),
    ],
)
class OrgRunnerGroupMembership(BaseAsset):
    runner_group_id: int
    runner_id: int
    accessible_repo_node_ids: list[str] = Field(default_factory=list)
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def _org_node_id(self) -> str:
        return self.org_node_id or self._lookup.org_id()

    @property
    def as_node(self):
        return None

    @property
    def _runner_node_id(self):
        return f"{self._org_node_id}_org_runner_{self.runner_id}"

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(
                value=f"{self._org_node_id}_runner_group_{self.runner_group_id}",
                match_by="id",
            ),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _can_use_runner_edges(self):
        for repo_node_id in self.accessible_repo_node_ids:
            yield Edge(
                kind=ek.CAN_USE_RUNNER,
                start=EdgePath(value=repo_node_id, match_by="id"),
                end=EdgePath(value=self._runner_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield from self._can_use_runner_edges
        yield from self._contains_edge


@app.asset(
    node=NodeDef(
        kind=nk.REPO_RUNNER,
        description="GitHub repository-scoped self-hosted runner",
        icon="microchip",
        properties=GHRunnerProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_RUNNER,
            kind=ek.CONTAINS,
            description="Repository contains repository runner",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.REPO_RUNNER,
            kind=ek.CAN_USE_RUNNER,
            description="Repository can dispatch jobs to repository runner",
            traversable=False,
        ),
    ],
)
class RepoRunner(BaseAsset):
    id: int
    name: str
    os: str | None = None
    status: str | None = None
    busy: bool | None = None
    ephemeral: bool | None = None
    labels: list[dict] = Field(default_factory=list)
    repository_name: str
    repository_node_id: str
    repository_full_name: str
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def node_id(self) -> str:
        return f"{self.repository_node_id}_repo_runner_{self.id}"

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.REPO_RUNNER, nk.RUNNER],
            properties=GHRunnerProperties(
                name=self.name,
                displayname=self.name,
                node_id=rid,
                scope="repository",
                runner_id=self.id,
                os=self.os,
                status=self.status,
                busy=self.busy,
                ephemeral=self.ephemeral,
                labels=json.dumps(self.labels),
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                repository_full_name=self.repository_full_name,
                environment_name=self.org_login or self._lookup.org_login(),
                environmentid=self.org_node_id or self._lookup.org_id(),
                query_repositories=f"MATCH p=(:GH_Repository {{node_id:'{self.repository_node_id}'}})-[:GH_CanUseRunner]->(:GH_RepoRunner {{node_id:'{rid}'}}) RETURN p",
            ),
        )

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _can_use_runner_edge(self):
        yield Edge(
            kind=ek.CAN_USE_RUNNER,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._can_use_runner_edge
        yield from self._contains_edge
