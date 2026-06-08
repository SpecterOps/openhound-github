from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, NodeDef
from pydantic import ConfigDict, Field

from openhound_github.graph import GHNode
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.team import GHTeamProperties


@app.asset(
    node=NodeDef(
        kind=nk.TEAM,
        description="GitHub Enterprise Projected Team",
        icon="user-group",
        properties=GHTeamProperties,
    ),
)
class ProjectedEnterpriseTeam(BaseAsset):
    """Additional models to map enterprise teams, since these are not discovered via the original GraphQL resource"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    node_id: str
    id: int | None = None
    name: str
    slug: str
    description: str | None = None
    privacy: str | None = Field(default=None)
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.TEAM],
            properties=GHTeamProperties(
                name=self.name,
                displayname=self.name,
                node_id=self.node_id,
                github_team_id=self.node_id,
                collected=False,
                slug=self.slug,
                description=self.description,
                privacy=self.privacy,
                type="enterprise",
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                query_repositories=f"MATCH p=(:GH_Team {{node_id:'{self.node_id}'}})-[:GH_HasRole]->(:GH_RepoRole)-[]->(:GH_Repository) RETURN p",
            ),
        )

    @property
    def edges(self):
        return []
