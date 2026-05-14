import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

import yaml  # type: ignore[import-untyped]
from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import (  # type: ignore[import-untyped]
    BaseAsset,
    EdgeDef,
    NodeDef,
)
from openhound.core.models.entries_dataclass import (  # type: ignore[import-untyped]
    Edge,
    EdgePath,
    EdgeProperties,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class GithubActionsLoader(yaml.SafeLoader):
    pass


GithubActionsLoader.yaml_implicit_resolvers = {
    key: list(value) for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for first, mappings in list(GithubActionsLoader.yaml_implicit_resolvers.items()):
    GithubActionsLoader.yaml_implicit_resolvers[first] = [
        (tag, regexp) for tag, regexp in mappings if tag != "tag:yaml.org,2002:bool"
    ]


SECRET_REFERENCE_RE = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
VARIABLE_REFERENCE_RE = re.compile(r"\$\{\{\s*vars\.(\w+)\s*\}\}")
ACTION_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<name>[^@]+)@(?P<ref>.+)$")
PINNED_REF_RE = re.compile(r"^[0-9a-f]{40}$")


class WorkflowStepDefinition(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str | None = None
    uses: str | None = None
    run: str | None = None
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    env: dict[str, Any] = Field(default_factory=dict)

    @field_validator("with_", "env", mode="before")
    @classmethod
    def dict_or_empty(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @property
    def display_name(self) -> str | None:
        if self.name:
            return self.name
        if self.uses:
            return self.uses
        if self.run:
            first_line = self.run.split("\n", 1)[0].strip()
            return f"{first_line[:80]}..." if len(first_line) > 80 else first_line
        return None

    @property
    def type(self) -> str:
        if self.uses:
            return "uses"
        if self.run:
            return "run"
        return "unknown"


class WorkflowJobDefinition(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    runs_on: Any = Field(default=None, alias="runs-on")
    needs: Any = None
    environment: Any = None
    permissions: Any = None
    uses: str | None = None
    container: Any = None
    env: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] | str | None = None
    steps: list[WorkflowStepDefinition] = Field(default_factory=list)

    @field_validator("env", mode="before")
    @classmethod
    def dict_or_empty(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @field_validator("steps", mode="before")
    @classmethod
    def valid_step_dicts(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [step for step in value if isinstance(step, dict)]

    @property
    def needs_list(self) -> list[str]:
        if isinstance(self.needs, str):
            return [self.needs]
        if isinstance(self.needs, list):
            return [str(item) for item in self.needs]
        return []

    @property
    def environment_name(self) -> str | None:
        if isinstance(self.environment, str):
            return self.environment
        if (
            isinstance(self.environment, dict)
            and self.environment.get("name") is not None
        ):
            return str(self.environment["name"])
        return None

    @property
    def is_self_hosted(self) -> bool:
        if isinstance(self.runs_on, str):
            return self.runs_on == "self-hosted"
        if isinstance(self.runs_on, list):
            return "self-hosted" in [str(item) for item in self.runs_on]
        return False


class WorkflowDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    permissions: Any = None
    jobs: dict[str, WorkflowJobDefinition] = Field(default_factory=dict)

    @field_validator("jobs", mode="before")
    @classmethod
    def jobs_dict_or_empty(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


def workflow_job_node_id(workflow_node_id: str, job_key: str) -> str:
    return f"GH_WorkflowJob_{workflow_node_id}_{job_key}"


def workflow_step_node_id(workflow_node_id: str, job_key: str, step_index: int) -> str:
    return f"GH_WorkflowStep_{workflow_node_id}_{job_key}_{step_index}"


def references(
    pattern: re.Pattern[str], text: Any, context: str
) -> list[dict[str, str]]:
    if text is None:
        return []
    return [
        {"name": name, "context": context}
        for name in dict.fromkeys(
            match.group(1) for match in pattern.finditer(str(text))
        )
    ]


def unique_references(items: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = []
    seen = set()
    for item in items:
        key = (item["name"], item.get("context"))
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def mapping_references(
    pattern: re.Pattern[str], mapping: dict[str, Any], context_prefix: str
) -> list[dict[str, str]]:
    refs = []
    for key, value in mapping.items():
        refs.extend(references(pattern, value, f"{context_prefix}:{key}"))
    return refs


def action_parts(action: str | None) -> dict[str, Any]:
    parts: dict[str, Any] = {
        "action_owner": None,
        "action_name": None,
        "action_ref": None,
        "action_slug": None,
        "is_pinned": False,
    }
    if not action:
        return parts
    match = ACTION_RE.match(action)
    if not match:
        return parts
    owner = match.group("owner")
    name = match.group("name")
    ref = match.group("ref")
    parts.update(
        {
            "action_owner": owner,
            "action_name": name,
            "action_ref": ref,
            "action_slug": f"{owner}/{name}",
            "is_pinned": bool(PINNED_REF_RE.match(ref)),
        }
    )
    return parts


@dataclass
class GHWorkflowProperties(GHNodeProperties):
    """Workflow-specific properties and accordion panel queries.

    Attributes:
        short_name: The workflow's display name.
        path: The file path of the workflow definition (e.g., `.github/workflows/ci.yml`).
        state: The workflow state (e.g., `active`, `disabled_manually`).
        url: The API URL for the workflow.
        repository_name: The full name of the containing repository.
        repository_id: The node_id of the containing repository.
        html_url: The GitHub web URL for the workflow file.
        branch: The branch where the workflow file was found.
        contents: The content of the workflow file.
        query_repository: Query for repository.
        query_editors: Query for editors.
        environment_name: The name of the environment (GitHub organization).
    """

    short_name: str | None = None
    path: str | None = None
    state: str | None = None
    url: str | None = None
    repository_name: str | None = None
    repository_id: str | None = None
    html_url: str | None = None
    branch: str | None = None
    contents: str | None = None
    query_repository: str | None = None
    query_editors: str | None = None
    environment_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.WORKFLOW,
        description="GitHub Actions Workflow",
        icon="cogs",
        properties=GHWorkflowProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.WORKFLOW,
            kind=ek.HAS_WORKFLOW,
            description="Repository contains workflow",
            traversable=False,
        ),
    ],
)
class Workflow(BaseAsset):
    """One record from `workflows` → one GH_Workflow node + GH_HasWorkflow edge from repo."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    id: int
    node_id: str
    name: str
    path: str
    state: str
    created_at: datetime
    updated_at: datetime
    url: str
    html_url: str | None = None
    branch: str | None = None
    contents: str | None = None
    # query_repository: str

    # Custom fields added
    org_login: str
    repository_name: str
    repository_node_id: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def document(self) -> WorkflowDocument | None:
        if not self.contents or not self.contents.strip():
            return None
        parsed = yaml.load(self.contents, Loader=GithubActionsLoader)
        if not isinstance(parsed, dict):
            return None
        try:
            return WorkflowDocument.model_validate(parsed)
        except ValidationError:
            return None

    def workflow_job_rows(self) -> list[dict[str, Any]]:
        document = self.document
        if not document:
            return []

        job_ids = {
            job_key: workflow_job_node_id(self.node_id, job_key)
            for job_key in document.jobs.keys()
        }
        rows = []
        for job_key, job in document.jobs.items():
            secret_refs = []
            variable_refs = []
            if isinstance(job.secrets, dict):
                secret_refs.extend(
                    mapping_references(SECRET_REFERENCE_RE, job.secrets, "secrets")
                )
            secret_refs.extend(mapping_references(SECRET_REFERENCE_RE, job.env, "env"))
            variable_refs.extend(
                mapping_references(VARIABLE_REFERENCE_RE, job.env, "env")
            )

            rows.append(
                {
                    "node_id": job_ids[job_key],
                    "name": f"{self.repository_name}\\{job_key}",
                    "job_key": job_key,
                    "runs_on": job.runs_on,
                    "is_self_hosted": job.is_self_hosted,
                    "container": job.container,
                    "environment": job.environment_name,
                    "permissions": job.permissions
                    if job.permissions is not None
                    else document.permissions,
                    "uses_reusable": job.uses,
                    "workflow_node_id": self.node_id,
                    "repository_name": self.repository_name,
                    "repository_node_id": self.repository_node_id,
                    "org_login": self.org_login,
                    "dependency_node_ids": [
                        job_ids[dep] for dep in job.needs_list if dep in job_ids
                    ],
                    "secret_references": unique_references(secret_refs),
                    "variable_references": unique_references(variable_refs),
                }
            )
        return rows

    def workflow_step_rows(self) -> list[dict[str, Any]]:
        document = self.document
        if not document:
            return []

        rows = []
        for job_key, job in document.jobs.items():
            job_node_id = workflow_job_node_id(self.node_id, job_key)
            for step_index, step in enumerate(job.steps):
                secret_refs = []
                variable_refs = []
                secret_refs.extend(
                    mapping_references(SECRET_REFERENCE_RE, step.with_, "with")
                )
                variable_refs.extend(
                    mapping_references(VARIABLE_REFERENCE_RE, step.with_, "with")
                )
                secret_refs.extend(references(SECRET_REFERENCE_RE, step.run, "run"))
                variable_refs.extend(references(VARIABLE_REFERENCE_RE, step.run, "run"))
                secret_refs.extend(
                    mapping_references(SECRET_REFERENCE_RE, step.env, "env")
                )
                variable_refs.extend(
                    mapping_references(VARIABLE_REFERENCE_RE, step.env, "env")
                )

                rows.append(
                    {
                        "node_id": workflow_step_node_id(
                            self.node_id, job_key, step_index
                        ),
                        "name": step.display_name,
                        "step_index": step_index,
                        "type": step.type,
                        "action": step.uses,
                        **action_parts(step.uses),
                        "run": step.run,
                        "with_args": step.with_ or None,
                        "contents": step.model_dump(by_alias=True, exclude_none=True),
                        "job_node_id": job_node_id,
                        "workflow_node_id": self.node_id,
                        "repository_name": self.repository_name,
                        "repository_node_id": self.repository_node_id,
                        "org_login": self.org_login,
                        "secret_references": unique_references(secret_refs),
                        "variable_references": unique_references(variable_refs),
                    }
                )
        return rows

    @property
    def as_node(self) -> GHNode:
        wid = self.node_id
        return GHNode(
            kinds=[nk.WORKFLOW],
            properties=GHWorkflowProperties(
                name=f"{self.repository_name}/{self.name}",
                displayname=self.name,
                node_id=wid,
                short_name=self.name,
                path=self.path,
                state=self.state,
                url=self.url,
                html_url=self.html_url,
                branch=self.branch,
                contents=self.contents,
                repository_name=self.repository_name,
                repository_id=self.repository_node_id,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_repository=f"MATCH p=(:GH_Repository)-[:GH_HasWorkflow]->(:GH_Workflow {{node_id:'{wid}'}}) RETURN p",
                query_editors=(
                    f"MATCH p=(role:GH_Role)-[:GH_HasRole|GH_HasBaseRole|GH_MemberOf|GH_WriteRepoContents|GH_WriteRepoPullRequests*1..]->"
                    f"(:GH_Repository)-[:GH_HasWorkflow]->(:GH_Workflow {{node_id:'{wid}'}}) "
                    f"MATCH p1=(role)<-[:GH_HasRole]-(:GH_User) RETURN p,p1"
                ),
            ),
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_WORKFLOW,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
