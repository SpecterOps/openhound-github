from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


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

    id: int
    node_id: str
    name: str
    path: str
    state: str
    created_at: datetime
    updated_at: datetime
    url: str
    # TODO: Check following three
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
    def as_node(self) -> GHNode:
        wid = self.node_id
        # short = self.short_name or self.name.rsplit("/", 1)[-1]
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
