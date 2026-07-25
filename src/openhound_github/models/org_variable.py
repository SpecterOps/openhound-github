from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


@dataclass
class GHOrgVariableProperties(GHNodeProperties):
    """Org variable properties and accordion panel queries.
    
    Attributes:
        visibility: The variable's visibility scope: `all` (all repos), `private` (private and internal repos), or `selected` (specific repos).
        environment_name: The name of the environment (GitHub organization).
        value: The plaintext value of the variable.
        created_at: When the variable was created.
        updated_at: When the variable was last updated.
        query_visible_repositories: Query for visible repositories.
    """

    visibility: str | None = None
    environment_name: str | None = None
    value: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    query_visible_repositories: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.ORG_VARIABLE,
        description="GitHub Organization Actions Variable",
        icon="lock-open",
        properties=GHOrgVariableProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.ORG_VARIABLE,
            kind=ek.CONTAINS,
            description="Org contains variable",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_VARIABLE,
            kind=ek.HAS_VARIABLE,
            description="Repository can access org variable",
            traversable=True,
        ),
    ],
)
class OrgVariable(BaseAsset):
    """One record from `organization_variables` → one GH_OrgVariable node + GH_Contains from org."""

    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    name: str
    value: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    visibility: str

    # Additional
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return f"GH_OrgVariable_{self.org_node_id}_{self.name}"

    @property
    def as_node(self) -> GHNode:
        vid = self.node_id
        return GHNode(
            kinds=[nk.ORG_VARIABLE, nk.VARIABLE],
            properties=GHOrgVariableProperties(
                name=self.name,
                displayname=self.name,
                node_id=vid,
                visibility=self.visibility,
                environment_name=self.org_login,
                environmentid=self.org_node_id,
                value=self.value,
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
                query_visible_repositories=f"MATCH p=(:GH_OrgVariable {{node_id:'{vid}'}})<-[:GH_HasVariable]-(:GH_Repository) RETURN p",
            ),
        )

    @property
    def _all_repo_edges(self):
        if self.visibility == "all":
            for repo in self._lookup.repository_node_ids_for_org(self.org_login):
                for repo_node_id in repo:
                    yield Edge(
                        kind=ek.HAS_VARIABLE,
                        start=EdgePath(value=repo_node_id, match_by="id"),
                        end=EdgePath(value=self.node_id, match_by="id"),
                        properties=EdgeProperties(traversable=True),
                    )

    @property
    def _private_repo_edges(self):
        if self.visibility == "private":
            for repo in self._lookup.private_repository_node_ids_for_org(
                self.org_login
            ):
                for repo_node_id in repo:
                    yield Edge(
                        kind=ek.HAS_VARIABLE,
                        start=EdgePath(value=repo_node_id, match_by="id"),
                        end=EdgePath(value=self.node_id, match_by="id"),
                        properties=EdgeProperties(traversable=True),
                    )

    @property
    def _contains_edge(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.org_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )

    @property
    def edges(self):
        yield from self._contains_edge
        yield from self._all_repo_edges
        yield from self._private_repo_edges


@app.asset(
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_VARIABLE,
            kind=ek.HAS_VARIABLE,
            description="Repository can access org variable",
            traversable=True,
        )
    ],
)
class SelectedOrgVariable(BaseAsset):
    """One record from `org_variable_repo_access` → GH_HasVariable edge (repo → variable). No node."""

    name: str
    repository_node_id: str
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def node_id(self) -> str:
        return f"GH_OrgVariable_{self.org_node_id}_{self.name}"

    @property
    def as_node(self):
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_VARIABLE,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=True),
        )
