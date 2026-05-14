from dataclasses import dataclass
from typing import Any, ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import (  # type: ignore[import-untyped]
    BaseAsset,
    EdgeDef,
    NodeDef,
)
from openhound.core.models.entries_dataclass import (  # type: ignore[import-untyped]
    ConditionalEdgePath,
    Edge,
    EdgePath,
    EdgeProperties,
    PropertyMatch,
)
from pydantic import BaseModel, Field

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class WorkflowReference(BaseModel):
    name: str
    context: str | None = None


@dataclass
class GHWorkflowJobProperties(GHNodeProperties):
    """Workflow job-specific properties.

    Attributes:
        job_key: The YAML key for the job.
        runs_on: The runner label expression for the job.
        is_self_hosted: Whether the job targets self-hosted runners.
        container: The optional container configuration.
        environment: The deployment environment name.
        permissions: Effective job permissions.
        uses_reusable: The reusable workflow reference used by this job.
        workflow_node_id: The parent workflow node ID.
        repository_name: The containing repository name.
        repository_id: The containing repository node ID.
        environment_name: The name of the GitHub organization.
    """

    job_key: str | None = None
    runs_on: Any = None
    is_self_hosted: bool = False
    container: Any = None
    environment: str | None = None
    permissions: Any = None
    uses_reusable: str | None = None
    workflow_node_id: str | None = None
    repository_name: str | None = None
    repository_id: str | None = None
    environment_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.WORKFLOW_JOB,
        description="GitHub Actions Workflow Job",
        icon="layer-group",
        properties=GHWorkflowJobProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.WORKFLOW,
            end=nk.WORKFLOW_JOB,
            kind=ek.HAS_JOB,
            description="Workflow contains job",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.WORKFLOW_JOB,
            kind=ek.DEPENDS_ON,
            description="Workflow job depends on another workflow job",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.ENVIRONMENT,
            kind=ek.DEPLOYS_TO,
            description="Workflow job deploys to environment",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.WORKFLOW,
            kind=ek.CALLS_WORKFLOW,
            description="Workflow job calls reusable workflow",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.REPO_SECRET,
            kind=ek.USES_SECRET,
            description="Workflow job references repository secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.ORG_SECRET,
            kind=ek.USES_SECRET,
            description="Workflow job references organization secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.REPO_VARIABLE,
            kind=ek.USES_VARIABLE,
            description="Workflow job references repository variable",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.ORG_VARIABLE,
            kind=ek.USES_VARIABLE,
            description="Workflow job references organization variable",
            traversable=False,
        ),
    ],
)
class WorkflowJob(BaseAsset):
    """One record from `workflow_jobs` -> one GH_WorkflowJob node."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    node_id: str
    name: str
    job_key: str
    workflow_node_id: str
    repository_name: str
    repository_node_id: str
    org_login: str
    runs_on: Any = None
    is_self_hosted: bool = False
    container: Any = None
    environment: str | None = None
    permissions: Any = None
    uses_reusable: str | None = None
    dependency_node_ids: list[str] = Field(default_factory=list)
    secret_references: list[WorkflowReference] = Field(default_factory=list)
    variable_references: list[WorkflowReference] = Field(default_factory=list)

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.WORKFLOW_JOB],
            properties=GHWorkflowJobProperties(
                name=self.name,
                displayname=self.job_key,
                node_id=self.node_id,
                job_key=self.job_key,
                runs_on=self.runs_on,
                is_self_hosted=self.is_self_hosted,
                container=self.container,
                environment=self.environment,
                permissions=self.permissions,
                uses_reusable=self.uses_reusable,
                workflow_node_id=self.workflow_node_id,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
            ),
        )

    @property
    def _uses_secret_edges(self):
        for ref in self.secret_references:
            yield Edge(
                kind=ek.USES_SECRET,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.REPO_SECRET,
                    property_matchers=[
                        PropertyMatch(key="name", value=ref.name),
                        PropertyMatch(
                            key="repository_id", value=self.repository_node_id
                        ),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.USES_SECRET,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.ORG_SECRET,
                    property_matchers=[
                        PropertyMatch(key="name", value=ref.name),
                        PropertyMatch(key="environmentid", value=self.org_node_id),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _uses_variable_edges(self):
        for ref in self.variable_references:
            yield Edge(
                kind=ek.USES_VARIABLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.REPO_VARIABLE,
                    property_matchers=[
                        PropertyMatch(key="name", value=ref.name),
                        PropertyMatch(
                            key="repository_id", value=self.repository_node_id
                        ),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )
            yield Edge(
                kind=ek.USES_VARIABLE,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.ORG_VARIABLE,
                    property_matchers=[
                        PropertyMatch(key="name", value=ref.name),
                        PropertyMatch(key="environmentid", value=self.org_node_id),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _has_job_edge(self):
        yield Edge(
            kind=ek.HAS_JOB,
            start=EdgePath(value=self.workflow_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def _dependency_edges(self):
        for dependency_node_id in self.dependency_node_ids:
            yield Edge(
                kind=ek.DEPENDS_ON,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=dependency_node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _environment_edges(self):
        if self.environment:
            yield Edge(
                kind=ek.DEPLOYS_TO,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.ENVIRONMENT,
                    property_matchers=[
                        PropertyMatch(
                            key="repository_id", value=self.repository_node_id
                        ),
                        PropertyMatch(key="short_name", value=self.environment),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _calls_workflows_edge(self):
        if self.uses_reusable and self.uses_reusable.startswith("./.github/workflows/"):
            yield Edge(
                kind=ek.CALLS_WORKFLOW,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=ConditionalEdgePath(
                    kind=nk.WORKFLOW,
                    property_matchers=[
                        PropertyMatch(
                            key="repository_id", value=self.repository_node_id
                        ),
                        PropertyMatch(key="path", value=self.uses_reusable[2:]),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def edges(self):
        yield from self._calls_workflows_edge
        yield from self._environment_edges
        yield from self._dependency_edges
        yield from self._has_job_edge
        yield from self._uses_secret_edges
        yield from self._uses_variable_edges
