from dataclasses import dataclass, field
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
    """Org variable properties and accordion panel queries."""

    visibility: str = field(
        default="",
        metadata={
            "description": "The variable's visibility scope: `all` (all repos), `private` (private and internal repos), or `selected` (specific repos)."
        },
    )
    environment_name: str = field(
        default="",
        metadata={"description": "The name of the environment (GitHub organization)."},
    )
    value: str | None = field(
        default=None, metadata={"description": "The plaintext value of the variable."}
    )
    created_at: str | None = field(
        default=None, metadata={"description": "When the variable was created."}
    )
    updated_at: str | None = field(
        default=None, metadata={"description": "When the variable was last updated."}
    )
    query_visible_repositories: str = ""


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
        org_node_id = self._org_node_id
        return f"GH_OrgVariable_{org_node_id}_{self.name}"

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
                environment_name=self._org_login,
                environmentid=self._org_node_id,
                value=self.value,
                created_at=str(self.created_at) if self.created_at else None,
                updated_at=str(self.updated_at) if self.updated_at else None,
                query_visible_repositories=f"MATCH p=(:GH_OrgVariable {{node_id:'{vid}'}})<-[:GH_HasVariable]-(:GH_Repository) RETURN p",
            ),
        )

    @property
    def edges(self):
        # TODO: Check if this should indeed not return CONTAINS edge
        return []
        # yield Edge(
        #         kind=ek.CONTAINS,
        #         start=EdgePath(value=self._lookup.org_id(), match_by="id"),
        #         end=EdgePath(value=self.node_id, match_by="id"),
        #         properties=EdgeProperties(traversable=False),
        #     )
        #


@app.asset(
    edges=[
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.ORG_VARIABLE,
            kind=ek.HAS_VARIABLE,
            description="Repository can access org variable",
            traversable=False,
        )
    ],
)
class SelectedOrgVariable(BaseAsset):
    """One record from `org_variable_repo_access` → GH_HasVariable edge (repo → variable). No node."""

    name: str
    repository_node_id: str
    org_node_id: str | None = None
    org_login: str | None = None

    @property
    def node_id(self) -> str:
        org_node_id = self.org_node_id or self._lookup.org_id()
        return f"GH_OrgVariable_{org_node_id}_{self.name}"

    @property
    def as_node(self):
        return None

    @property
    def edges(self):
        yield Edge(
            kind=ek.HAS_VARIABLE,
            start=EdgePath(value=self.repository_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
