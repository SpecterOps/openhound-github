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


_ALL_REPOSITORY_CREATION_EDGE_KINDS = (
    ek.CAN_CREATE_REPOSITORIES,
    ek.CAN_CREATE_PUBLIC_REPOSITORIES,
    ek.CAN_CREATE_INTERNAL_REPOSITORIES,
    ek.CAN_CREATE_PRIVATE_REPOSITORIES,
)
_PRIVATE_REPOSITORY_CREATION_EDGE_KINDS = (
    ek.CAN_CREATE_INTERNAL_REPOSITORIES,
    ek.CAN_CREATE_PRIVATE_REPOSITORIES,
)


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
        query_organizations: Query for organizations inheriting an enterprise runner group.
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
            traversable=True,
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
            f"MATCH p=(:GH_OrgRunnerGroup {{node_id:'{gid}'}})-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup)-[:GH_HasRunner]->(:GH_EnterpriseRunner) RETURN p"
            if self.inherited
            else f"MATCH p=(:GH_OrgRunnerGroup {{node_id:'{gid}'}})-[:GH_HasRunner]->(:GH_OrgRunner) RETURN p"
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
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_IsEligibleFor]->(:GH_OrgRunnerGroup {{node_id:'{gid}'}}) RETURN p",
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
                    properties=EdgeProperties(traversable=True),
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
                query_runners=f"MATCH p=(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}})-[:GH_HasRunner]->(:GH_EnterpriseRunner) RETURN p",
                query_organizations=f"MATCH p=(:GH_Organization)-[:GH_Contains]->(:GH_OrgRunnerGroup)-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_IsEligibleFor]->(:GH_OrgRunnerGroup)-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup {{node_id:'{gid}'}}) RETURN p",
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
    description="Maps an enterprise runner group to an organization without emitting a node."
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
        return []


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
                query_group=f"MATCH p=(:GH_OrgRunnerGroup)-[:GH_HasRunner]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_OrgRunnerGroup)-[:GH_HasRunner]->(:GH_OrgRunner {{node_id:'{rid}'}}) RETURN p",
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
                query_group=f"MATCH p=(:GH_EnterpriseRunnerGroup)-[:GH_HasRunner]->(:GH_EnterpriseRunner {{node_id:'{rid}'}}) RETURN p",
                query_repositories=f"MATCH p=(:GH_Repository)-[:GH_CanUseRunner]->(:GH_OrgRunnerGroup)-[:GH_InheritedFrom]->(:GH_EnterpriseRunnerGroup)-[:GH_HasRunner]->(:GH_EnterpriseRunner {{node_id:'{rid}'}}) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []


@app.asset(
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.IS_ELIGIBLE_FOR,
            description="Repository is eligible for organization runner group based on repository access policy",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.CAN_USE_RUNNER,
            description="Repository can dispatch workflows to organization runner group",
            traversable=True,
        ),
        EdgeDef(
            start=nk.BRANCH,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.CAN_USE_RUNNER,
            description="Branch can dispatch workflows to organization runner group",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
            description="Org role can create a repository that can dispatch workflows to this runner group",
            traversable=True,
        ),
    ],
)
class OrgRunnerGroupAccess(BaseAsset):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    runner_group_id: int
    runner_group_name: str
    runner_group_visibility: str | None = None
    allows_public_repositories: bool | None = None
    restricted_to_workflows: bool | None = None
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

    @property
    def _repository_creation_edge_kinds(self) -> tuple[str, ...]:
        if self.runner_group_visibility == "all":
            if self.allows_public_repositories is False:
                return _PRIVATE_REPOSITORY_CREATION_EDGE_KINDS
            return _ALL_REPOSITORY_CREATION_EDGE_KINDS
        if self.runner_group_visibility == "private":
            return _PRIVATE_REPOSITORY_CREATION_EDGE_KINDS
        return ()

    def _members_can_create_repository_in_scope(
        self, edge_kinds: tuple[str, ...]
    ) -> bool:
        creation_flags = self._lookup.members_can_create_repository(self.org_login)
        if not creation_flags:
            return False

        permissions = dict(zip(_ALL_REPOSITORY_CREATION_EDGE_KINDS, creation_flags))
        return any(bool(permissions.get(edge_kind)) for edge_kind in edge_kinds)

    def _can_create_repository_with_runner_access_query(
        self, role_node_id: str, edge_kinds: tuple[str, ...]
    ) -> str:
        creation_edges = "|".join(edge_kinds)
        inherited_path = (
            "-[:GH_InheritedFrom]->(enterprise_group:GH_EnterpriseRunnerGroup)"
            if self.inherited
            else ""
        )
        conditions = [
            "org.actions_enabled_repositories = 'all'",
            "coalesce(group.restricted_to_workflows, true) = false",
        ]
        if self.inherited:
            conditions.append(
                "coalesce(enterprise_group.restricted_to_workflows, true) = false"
            )
        return (
            f"MATCH p=(:GH_OrgRole {{node_id:'{role_node_id}'}})"
            f"-[:{creation_edges}]->"
            "(org:GH_Organization)-[:GH_Contains]->"
            f"(group:GH_OrgRunnerGroup {{node_id:'{self.runner_group_node_id}'}})"
            f"{inherited_path} "
            f"WHERE {' AND '.join(conditions)} RETURN p"
        )

    @property
    def _workflow_policy_allows_repository_dispatch(self) -> bool:
        if self.restricted_to_workflows is not False:
            return False

        if not self.inherited:
            return True

        return (
            self._lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group(
                self.org_node_id, self.runner_group_name
            )
            is False
        )

    @property
    def _can_use_runner_repository_node_ids(self) -> list[str]:
        if not self._workflow_policy_allows_repository_dispatch:
            return []

        actions_enabled_repository_node_ids = {
            repository_node_id
            for (
                repository_node_id,
            ) in self._lookup.actions_enabled_repository_node_ids_for_org(
                self.org_login
            )
        }
        return [
            repository_node_id
            for (repository_node_id,) in self.repository_node_ids
            if repository_node_id in actions_enabled_repository_node_ids
        ]

    @property
    def _new_repositories_can_dispatch_workflows(self) -> bool:
        return (
            self._workflow_policy_allows_repository_dispatch
            and self._lookup.actions_enabled_repositories_for_org(self.org_login)
            == "all"
        )

    @property
    def _is_eligible_for_edges(self):
        for (repo_node_id,) in self.repository_node_ids:
            yield Edge(
                kind=ek.IS_ELIGIBLE_FOR,
                start=EdgePath(value=repo_node_id, match_by="id"),
                end=EdgePath(value=self.runner_group_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _can_use_runner_edges(self):
        repository_node_ids = self._can_use_runner_repository_node_ids
        if not repository_node_ids:
            return

        repository_node_id_set = set(repository_node_ids)
        for repository_node_id in repository_node_ids:
            yield Edge(
                kind=ek.CAN_USE_RUNNER,
                start=EdgePath(value=repository_node_id, match_by="id"),
                end=EdgePath(value=self.runner_group_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

        for repository_node_id, branch_node_id in self._lookup.branch_node_ids_for_org(
            self.org_login
        ):
            if repository_node_id not in repository_node_id_set:
                continue

            yield Edge(
                kind=ek.CAN_USE_RUNNER,
                start=EdgePath(value=branch_node_id, match_by="id"),
                end=EdgePath(value=self.runner_group_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

    @property
    def _can_create_repository_with_runner_access_edges(self):
        edge_kinds = self._repository_creation_edge_kinds
        if not edge_kinds or not self._new_repositories_can_dispatch_workflows:
            return

        owners_role_id = f"{self.org_node_id}_owners"
        yield Edge(
            kind=ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
            start=EdgePath(value=owners_role_id, match_by="id"),
            end=EdgePath(value=self.runner_group_node_id, match_by="id"),
            properties=GHEdgeProperties(
                traversable=True,
                composed=True,
                query_composition=self._can_create_repository_with_runner_access_query(
                    owners_role_id, edge_kinds
                ),
            ),
        )

        if self._members_can_create_repository_in_scope(edge_kinds):
            members_role_id = f"{self.org_node_id}_members"
            yield Edge(
                kind=ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
                start=EdgePath(value=members_role_id, match_by="id"),
                end=EdgePath(value=self.runner_group_node_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    query_composition=self._can_create_repository_with_runner_access_query(
                        members_role_id, edge_kinds
                    ),
                ),
            )

    @property
    def edges(self):
        yield from self._is_eligible_for_edges
        yield from self._can_use_runner_edges
        yield from self._can_create_repository_with_runner_access_edges


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
            start=nk.ORG_RUNNER_GROUP,
            end=nk.ORG_RUNNER,
            kind=ek.HAS_RUNNER,
            description="Organization runner group exposes organization runner to authorized repositories",
            traversable=True,
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

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self._runner_group_node_id, match_by="id"),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _has_runner_edge(self):
        yield Edge(
            kind=ek.HAS_RUNNER,
            start=EdgePath(value=self._runner_group_node_id, match_by="id"),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )

    @property
    def edges(self):
        yield from self._contains_edge
        yield from self._has_runner_edge


@app.asset(
    edges=[
        EdgeDef(
            start=nk.ENTERPRISE_RUNNER_GROUP,
            end=nk.ENTERPRISE_RUNNER,
            kind=ek.CONTAINS,
            description="Enterprise runner group contains enterprise runner",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ENTERPRISE_RUNNER_GROUP,
            end=nk.ENTERPRISE_RUNNER,
            kind=ek.HAS_RUNNER,
            description="Enterprise runner group exposes enterprise runner to authorized repositories",
            traversable=True,
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
        yield Edge(
            kind=ek.HAS_RUNNER,
            start=EdgePath(value=self._runner_group_node_id, match_by="id"),
            end=EdgePath(value=self._runner_node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
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
