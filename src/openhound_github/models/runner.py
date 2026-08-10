import json
from dataclasses import dataclass
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import Field

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.runner_ids import runner_group_node_id, runner_node_id


@dataclass
class GHRunnerGroupProperties(GHNodeProperties):
    """Properties for GHRunnerGroupProperties.
    
    Attributes:
        scope: Whether the runner group is enterprise or organization scoped.
        group_id: The GitHub runner group ID.
        group_name: The runner group display name.
        visibility: Which repositories can use this group: `all`, `private`, or `selected`.
        default: Whether this is the default runner group.
        inherited: Whether this runner group is inherited.
        allows_public_repositories: Whether public repositories may use this group.
        restricted_to_workflows: Whether access is restricted to selected workflows.
        selected_workflows: JSON array of selected workflows, if configured.
        runners_url: API URL for runners in this group.
        selected_organizations_url: API URL for organizations assigned to an enterprise group.
        environment_name: The name of the environment (GitHub organization or enterprise).
        query_runners: Query for runners.
        query_organizations: Query for organizations assigned to an enterprise group.
        query_repositories: Query for repositories.
    """

    scope: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    visibility: str | None = None
    default: bool | None = None
    inherited: bool | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
    selected_workflows: str | None = None
    runners_url: str | None = None
    selected_organizations_url: str | None = None
    environment_name: str | None = None
    query_runners: str | None = None
    query_organizations: str | None = None
    query_repositories: str | None = None


def _runner_group_repository_node_ids(
    lookup,
    org_login: str,
    visibility: str | None,
    allows_public_repositories: bool | None,
    accessible_repo_node_ids: list[str],
):
    if visibility == "all":
        if allows_public_repositories is False:
            return lookup.private_repository_node_ids_for_org(org_login)
        return lookup.repository_node_ids_for_org(org_login)

    if visibility == "private":
        return lookup.private_repository_node_ids_for_org(org_login)

    repo_node_ids = [(repo_node_id,) for repo_node_id in accessible_repo_node_ids]
    if allows_public_repositories is not False:
        return repo_node_ids

    private_repo_node_ids = set(lookup.private_repository_node_ids_for_org(org_login))
    return [
        (repo_node_id,)
        for (repo_node_id,) in repo_node_ids
        if (repo_node_id,) in private_repo_node_ids
    ]


@app.asset(
    node=NodeDef(
        kind=nk.ORG_RUNNER_GROUP,
        description="GitHub organization-scoped self-hosted runner group",
        icon="server",
        properties=GHRunnerGroupProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.CONTAINS,
            description="Organization contains organization runner group",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_RUNNER_GROUP,
            end=nk.ENTERPRISE_RUNNER_GROUP,
            kind=ek.INHERITED_FROM,
            description="Organization runner group is inherited from enterprise runner group",
            traversable=False,
        ),
    ],
)
class OrgRunnerGroup(BaseAsset):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    name: str
    visibility: str | None = None
    default: bool | None = None
    inherited: bool | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
    selected_workflows: list[str] | None = None
    runners_url: str | None = None

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return runner_group_node_id(self.org_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        gid = self.node_id
        query_runners = (
            f"MATCH p=(:GH_OrgRunnerGroup {{node_id:'{gid}'}})-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup)-[:GH_Contains]->(:GH_EnterpriseRunner) RETURN p"
            if self.inherited
            else f"MATCH p=(:GH_OrgRunnerGroup {{node_id:'{gid}'}})-[:GH_Contains]->(:GH_OrgRunner) RETURN p"
        )
        return GHNode(
            kinds=[nk.ORG_RUNNER_GROUP, nk.RUNNER_GROUP],
            properties=GHRunnerGroupProperties(
                name=f"{self.org_login}/{self.name}",
                displayname=self.name,
                node_id=gid,
                scope="organization",
                group_id=self.id,
                group_name=self.name,
                visibility=self.visibility,
                default=self.default,
                inherited=self.inherited,
                allows_public_repositories=self.allows_public_repositories,
                restricted_to_workflows=self.restricted_to_workflows,
                selected_workflows=json.dumps(self.selected_workflows or []),
                runners_url=self.runners_url,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_runners=query_runners,
                query_repositories=f"MATCH p=(:GH_OrgRunnerGroup {{node_id:'{gid}'}})-[:GH_GrantsAccessTo]->(:GH_Repository) RETURN p",
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        if self.inherited:
            enterprise_runner_group_node_id = (
                self._lookup.enterprise_runner_group_node_id_for_inherited_org_group(
                    self.org_node_id, self.name
                )
            )
            if enterprise_runner_group_node_id:
                yield Edge(
                    kind=ek.INHERITED_FROM,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(
                        value=enterprise_runner_group_node_id,
                        match_by="id",
                    ),
                    properties=EdgeProperties(traversable=False),
                )


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_RUNNER_GROUP,
        description="GitHub enterprise-scoped self-hosted runner group",
        icon="server",
        properties=GHRunnerGroupProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE,
            end=nk.ENTERPRISE_RUNNER_GROUP,
            kind=ek.CONTAINS,
            description="Enterprise contains enterprise runner group",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_RUNNER_GROUP,
            end=nk.ORGANIZATION,
            kind=ek.ASSIGNED_TO,
            description="Enterprise runner group is assigned to organization",
            traversable=False,
        ),
    ],
)
class EnterpriseRunnerGroup(BaseAsset):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    name: str
    visibility: str | None = None
    default: bool | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
    selected_workflows: list[str] | None = None
    runners_url: str | None = None
    selected_organizations_url: str | None = None

    # Additional
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return runner_group_node_id(self.enterprise_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        gid = self.node_id
        return GHNode(
            kinds=[nk.ENTERPRISE_RUNNER_GROUP, nk.RUNNER_GROUP],
            properties=GHRunnerGroupProperties(
                name=f"{self.enterprise_slug}/{self.name}",
                displayname=self.name,
                node_id=gid,
                scope="enterprise",
                group_id=self.id,
                group_name=self.name,
                visibility=self.visibility,
                default=self.default,
                allows_public_repositories=self.allows_public_repositories,
                restricted_to_workflows=self.restricted_to_workflows,
                selected_workflows=json.dumps(self.selected_workflows or []),
                runners_url=self.runners_url,
                selected_organizations_url=self.selected_organizations_url,
                environment_name=self.enterprise_slug,
                environmentid=self.enterprise_node_id,
                query_runners=f"MATCH p=(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}})-[:GH_Contains]->(:GH_EnterpriseRunner) RETURN p",
                query_organizations=f"MATCH p=(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}})-[:GH_AssignedTo]->(:GH_Organization) RETURN p",
                query_repositories=f"MATCH p=(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}})<-[:GH_InheritedFrom]-(:GH_OrgRunnerGroup)-[:GH_GrantsAccessTo]->(:GH_Repository) RETURN p",
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
        if self.visibility == "all":
            for (organization_node_id,) in self._lookup.enterprise_organization_node_ids(
                self.enterprise_node_id
            ):
                yield Edge(
                    kind=ek.ASSIGNED_TO,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=EdgePath(value=organization_node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_RUNNER_GROUP,
            end=nk.ORGANIZATION,
            kind=ek.ASSIGNED_TO,
            description="Enterprise runner group is assigned to organization",
            traversable=False,
        ),
    ],
)
class EnterpriseRunnerGroupOrganization(BaseAsset):
    node_id: str
    login: str | None = None
    runner_group_id: int
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self):
        return None

    @property
    def enterprise_runner_group_node_id(self) -> str:
        return runner_group_node_id(self.enterprise_node_id, self.runner_group_id)

    @property
    def edges(self):
        yield Edge(
            kind=ek.ASSIGNED_TO,
            start=EdgePath(value=self.enterprise_runner_group_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


@dataclass
class GHRunnerProperties(GHNodeProperties):
    """Properties for GHRunnerProperties.
    
    Attributes:
        scope: Whether the runner is enterprise, organization, or repository scoped.
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
        query_group: Query for group.
        query_repositories: Query for repositories.
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

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return runner_node_id(self.org_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.ORG_RUNNER, nk.RUNNER],
            properties=GHRunnerProperties(
                name=f"{self.org_login}/{self.name}",
                displayname=self.name,
                node_id=rid,
                scope="organization",
                runner_id=self.id,
                os=self.os,
                status=self.status,
                busy=self.busy,
                ephemeral=self.ephemeral,
                labels=json.dumps(self.labels),
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_group=f"MATCH p=(:GH_OrgRunnerGroup)-[:GH_Contains]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []


@app.asset(
    node=NodeDef(
        kind=nk.ENTERPRISE_RUNNER,
        description="GitHub enterprise-scoped self-hosted runner",
        icon="microchip",
        properties=GHRunnerProperties,
    )
)
class EnterpriseRunner(BaseAsset):
    id: int
    name: str
    os: str | None = None
    status: str | None = None
    busy: bool | None = None
    ephemeral: bool | None = None
    labels: list[dict] = Field(default_factory=list)

    # Additional
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def node_id(self) -> str:
        return runner_node_id(self.enterprise_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.ENTERPRISE_RUNNER, nk.RUNNER],
            properties=GHRunnerProperties(
                name=f"{self.enterprise_slug}/{self.name}",
                displayname=self.name,
                node_id=rid,
                scope="enterprise",
                runner_id=self.id,
                os=self.os,
                status=self.status,
                busy=self.busy,
                ephemeral=self.ephemeral,
                labels=json.dumps(self.labels),
                environment_name=self.enterprise_slug,
                environmentid=self.enterprise_node_id,
                query_group=f"MATCH p=(:GH_EnterpriseRunnerGroup)-[:GH_Contains]->(:GH_EnterpriseRunner {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_EnterpriseRunner {{node_id:'{rid}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ORG_RUNNER_GROUP,
            end=nk.REPOSITORY,
            kind=ek.GRANTS_ACCESS_TO,
            description="Organization runner group grants repository access to runners",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ENTERPRISE_RUNNER,
            kind=ek.CAN_USE_RUNNER,
            description="Repository can dispatch jobs to inherited enterprise runner",
            traversable=False,
        ),
    ],
)
class OrgRunnerGroupAccess(BaseAsset):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    runner_group_id: int
    runner_group_name: str
    runner_group_visibility: str | None = None
    allows_public_repositories: bool | None = None
    inherited: bool | None = None
    accessible_repo_node_ids: list[str] = Field(default_factory=list)

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def runner_group_node_id(self) -> str:
        return runner_group_node_id(self.org_node_id, self.runner_group_id)

    @property
    def as_node(self):
        return None

    @property
    def repository_node_ids(self):
        return _runner_group_repository_node_ids(
            self._lookup,
            self.org_login,
            self.runner_group_visibility,
            self.allows_public_repositories,
            self.accessible_repo_node_ids,
        )

    def _inherited_can_use_runner_query(
        self, repository_node_id: str, runner_node_id: str
    ) -> str:
        return (
            f"MATCH p=(:GH_Repository {{node_id:'{repository_node_id}'}})"
            f"<-[:GH_GrantsAccessTo]-(:GH_OrgRunnerGroup {{node_id:'{self.runner_group_node_id}'}})"
            "-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup)"
            f"-[:GH_Contains]->(:GH_EnterpriseRunner {{node_id:'{runner_node_id}'}}) RETURN p"
        )

    @property
    def _grants_access_to_edges(self):
        for (repo_node_id,) in self.repository_node_ids:
            yield Edge(
                kind=ek.GRANTS_ACCESS_TO,
                start=EdgePath(value=self.runner_group_node_id, match_by="id"),
                end=EdgePath(value=repo_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _inherited_can_use_runner_edges(self):
        if not self.inherited:
            return

        runner_node_ids = (
            self._lookup.enterprise_runner_node_ids_for_inherited_org_group(
                self.org_node_id, self.runner_group_name
            )
        )
        for (repo_node_id,) in self.repository_node_ids:
            for (enterprise_runner_node_id,) in runner_node_ids:
                yield Edge(
                    kind=ek.CAN_USE_RUNNER,
                    start=EdgePath(value=repo_node_id, match_by="id"),
                    end=EdgePath(value=enterprise_runner_node_id, match_by="id"),
                    properties=GHEdgeProperties(
                        traversable=False,
                        composed=True,
                        query_composition=self._inherited_can_use_runner_query(
                            repo_node_id, enterprise_runner_node_id
                        ),
                    ),
                )

    @property
    def edges(self):
        yield from self._grants_access_to_edges
        yield from self._inherited_can_use_runner_edges


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ORG_RUNNER_GROUP,
            end=nk.ORG_RUNNER,
            kind=ek.CONTAINS,
            description="Organization runner group contains organization runner",
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
    runner_group_name: str | None = None
    runner_id: int
    runner_group_visibility: str | None = None
    allows_public_repositories: bool | None = None
    accessible_repo_node_ids: list[str] = Field(default_factory=list)

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self):
        return None

    @property
    def _runner_node_id(self):
        return runner_node_id(self.org_node_id, self.runner_id)

    @property
    def _runner_group_node_id(self):
        return runner_group_node_id(self.org_node_id, self.runner_group_id)

    def _can_use_runner_query(self, repository_node_id: str) -> str:
        return (
            f"MATCH p=(:GH_Repository {{node_id:'{repository_node_id}'}})"
            f"<-[:GH_GrantsAccessTo]-(:GH_OrgRunnerGroup {{node_id:'{self._runner_group_node_id}'}})"
            f"-[:GH_Contains]->(:GH_OrgRunner {{node_id:'{self._runner_node_id}'}}) RETURN p"
        )

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._runner_group_node_id, match_by="id"),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _can_use_runner_edges(self):
        repo_node_ids = _runner_group_repository_node_ids(
            self._lookup,
            self.org_login,
            self.runner_group_visibility,
            self.allows_public_repositories,
            self.accessible_repo_node_ids,
        )

        for (repo_node_id,) in repo_node_ids:
            yield Edge(
                kind=ek.CAN_USE_RUNNER,
                start=EdgePath(value=repo_node_id, match_by="id"),
                end=EdgePath(value=self._runner_node_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=False,
                    composed=True,
                    query_composition=self._can_use_runner_query(repo_node_id),
                ),
            )

    @property
    def edges(self):
        yield from self._can_use_runner_edges
        yield from self._contains_edge


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_RUNNER_GROUP,
            end=nk.ENTERPRISE_RUNNER,
            kind=ek.CONTAINS,
            description="Enterprise runner group contains enterprise runner",
            traversable=False,
        ),
    ],
)
class EnterpriseRunnerGroupMembership(BaseAsset):
    runner_group_id: int
    runner_id: int

    # Additional
    enterprise_node_id: str
    enterprise_slug: str

    @property
    def as_node(self):
        return None

    @property
    def _runner_group_node_id(self) -> str:
        return runner_group_node_id(self.enterprise_node_id, self.runner_group_id)

    @property
    def _runner_node_id(self) -> str:
        return runner_node_id(self.enterprise_node_id, self.runner_id)

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._runner_group_node_id, match_by="id"),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )


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

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return runner_node_id(self.repository_node_id, self.id)

    @property
    def as_node(self) -> GHNode:
        rid = self.node_id
        return GHNode(
            kinds=[nk.REPO_RUNNER, nk.RUNNER],
            properties=GHRunnerProperties(
                name=f"{self.repository_full_name}/{self.name}",
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
                environment_name=self.org_login,
                environmentid=self.org_node_id,
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
