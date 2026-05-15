import json
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
class GHWorkflowStepProperties(GHNodeProperties):
    """Workflow step-specific properties.

    Attributes:
        step_index: The zero-based step index within the parent job.
        type: The step type: `uses`, `run`, or `unknown`.
        action: The full action reference from `uses`.
        action_slug: The action owner/name without ref.
        action_owner: The action owner.
        action_name: The action name.
        action_ref: The action ref.
        is_pinned: Whether the action ref is a full commit SHA.
        run: The shell command body for `run` steps.
        with_args: The step `with` arguments.
        contents: The full parsed step definition.
        job_node_id: The parent workflow job node ID.
        workflow_node_id: The parent workflow node ID.
        repository_name: The containing repository name.
        repository_id: The containing repository node ID.
        environment_name: The name of the GitHub organization.
    """

    step_index: int | None = None
    type: str | None = None
    action: str | None = None
    action_slug: str | None = None
    action_owner: str | None = None
    action_name: str | None = None
    action_ref: str | None = None
    is_pinned: bool = False
    run: str | None = None
    contents: str | None = None
    job_node_id: str | None = None
    workflow_node_id: str | None = None
    repository_name: str | None = None
    repository_id: str | None = None
    environment_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.WORKFLOW_STEP,
        description="GitHub Actions Workflow Step",
        icon="circle-dot",
        properties=GHWorkflowStepProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.WORKFLOW_JOB,
            end=nk.WORKFLOW_STEP,
            kind=ek.HAS_STEP,
            description="Workflow job contains step",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_STEP,
            end=nk.REPO_SECRET,
            kind=ek.USES_SECRET,
            description="Workflow step references repository secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_STEP,
            end=nk.ORG_SECRET,
            kind=ek.USES_SECRET,
            description="Workflow step references organization secret",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_STEP,
            end=nk.REPO_VARIABLE,
            kind=ek.USES_VARIABLE,
            description="Workflow step references repository variable",
            traversable=False,
        ),
        EdgeDef(
            start=nk.WORKFLOW_STEP,
            end=nk.ORG_VARIABLE,
            kind=ek.USES_VARIABLE,
            description="Workflow step references organization variable",
            traversable=False,
        ),
    ],
)
class WorkflowStep(BaseAsset):
    """One record from `workflow_steps` -> one GH_WorkflowStep node."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    node_id: str
    name: str | None = None
    step_index: int
    type: str
    job_node_id: str
    workflow_node_id: str
    repository_name: str
    repository_node_id: str
    org_login: str
    action: str | None = None
    action_slug: str | None = None
    action_owner: str | None = None
    action_name: str | None = None
    action_ref: str | None = None
    is_pinned: bool = False
    run: str | None = None
    with_args: dict[str, Any] | None = None
    contents: dict[str, Any] | None = None
    secret_references: list[WorkflowReference] = Field(default_factory=list)
    variable_references: list[WorkflowReference] = Field(default_factory=list)

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self) -> GHNode:
        name = self.name or f"step-{self.step_index}"
        return GHNode(
            kinds=[nk.WORKFLOW_STEP],
            properties=GHWorkflowStepProperties(
                name=name,
                displayname=name,
                node_id=self.node_id,
                step_index=self.step_index,
                type=self.type,
                action=self.action,
                action_slug=self.action_slug,
                action_owner=self.action_owner,
                action_name=self.action_name,
                action_ref=self.action_ref,
                is_pinned=self.is_pinned,
                run=self.run,
                contents=json.dumps(self.contents),
                job_node_id=self.job_node_id,
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
            if self._lookup.repo_secret(ref.name, self.repository_node_id):
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
            if self._lookup.org_secret(ref.name, self.org_login):
                yield Edge(
                    kind=ek.USES_SECRET,
                    start=EdgePath(value=self.node_id, match_by="id"),
                    end=ConditionalEdgePath(
                        kind=nk.ORG_SECRET,
                        property_matchers=[
                            PropertyMatch(key="name", value=ref.name),
                            PropertyMatch(
                                key="environmentid", value=self.org_node_id.upper()
                            ),
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
                        PropertyMatch(
                            key="environmentid", value=self.org_node_id.upper()
                        ),
                    ],
                ),
                properties=EdgeProperties(traversable=False),
            )

    @property
    def _has_step_edge(self):
        yield Edge(
            kind=ek.HAS_STEP,
            start=EdgePath(value=self.job_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._has_step_edge
        yield from self._uses_secret_edges
        yield from self._uses_variable_edges
