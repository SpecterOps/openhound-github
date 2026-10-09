from dataclasses import dataclass

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


ALL_REPOSITORIES_SCOPE = "all"
PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE = "private_or_internal"
REPOSITORY_SCOPE_TYPE = "repository"
RUNNER_GROUP_SCOPE_TYPE = "runner_group"
ORGANIZATION_SECRET_SCOPE_TYPE = "organization_secret"
ORGANIZATION_VARIABLE_SCOPE_TYPE = "organization_variable"

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


def scope_node_id(org_node_id: str, scope_type: str, scope: str) -> str:
    return f"GH_Scope_{org_node_id}_{scope_type}_{scope}"


@dataclass
class GHScopeProperties(GHNodeProperties):
    collected: bool = True
    scope_type: str | None = None
    scope: str | None = None
    member_count: int | None = None
    environment_name: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.SCOPE,
        description="Reusable asset selection within a GitHub organization",
        icon="boxes-stacked",
        properties=GHScopeProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.SCOPE,
            kind=ek.CONTAINS,
            description="Organization contains repository scope",
            traversable=False,
        ),
        EdgeDef(
            start=nk.SCOPE,
            end=nk.REPOSITORY,
            kind=ek.SCOPED_TO,
            description="Repository scope applies to repository",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCOPE,
            end=nk.ORG_RUNNER_GROUP,
            kind=ek.SCOPED_TO,
            description="Runner-group scope applies to organization runner group",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCOPE,
            end=nk.ORG_SECRET,
            kind=ek.SCOPED_TO,
            description="Organization-secret scope applies to organization secret",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.SCOPE,
            kind=ek.HAS_SECRET,
            description="Repository has access to organization-secret scope",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SCOPE,
            end=nk.ORG_VARIABLE,
            kind=ek.SCOPED_TO,
            description="Organization-variable scope applies to organization variable",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.SCOPE,
            kind=ek.HAS_VARIABLE,
            description="Repository has access to organization-variable scope",
            traversable=True,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.SCOPE,
            kind=ek.IS_ELIGIBLE_FOR,
            description="Repository is eligible for runner-group scope",
            traversable=False,
        ),
        EdgeDef(
            start=nk.APP_INSTALLATION,
            end=nk.SCOPE,
            kind=ek.CAN_ACCESS,
            description="App installation can access repository scope",
            traversable=False,
        ),
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN,
            end=nk.SCOPE,
            kind=ek.CAN_ACCESS,
            description="PAT can access repository scope",
            traversable=False,
        ),
        EdgeDef(
            start=nk.PERSONAL_ACCESS_TOKEN_REQUEST,
            end=nk.SCOPE,
            kind=ek.REQUESTS_ACCESS_TO,
            description="Pending PAT request requests access to repository scope",
            traversable=False,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.SCOPE,
            kind=ek.CAN_READ_SECRET,
            description=(
                "Org role can read secrets in an organization-secret scope by "
                "creating a repository in scope"
            ),
            traversable=True,
        ),
    ],
)
class Scope(BaseAsset):
    org_node_id: str
    org_login: str
    scope_type: str
    scope: str

    @property
    def node_id(self) -> str:
        return scope_node_id(self.org_node_id, self.scope_type, self.scope)

    @property
    def as_node(self) -> GHNode:
        qualified_name = f"{self.org_login}/{self.scope_type}/{self.scope}"
        return GHNode(
            kinds=[nk.SCOPE],
            properties=GHScopeProperties(
                name=qualified_name,
                displayname=qualified_name,
                node_id=self.node_id,
                scope_type=self.scope_type,
                scope=self.scope,
                member_count=self._lookup.canonical_scope_target_count(
                    self.org_login, self.scope_type, self.scope
                ),
                environment_name=self.org_login,
                environmentid=self.org_node_id,
            ),
        )

    @property
    def _repository_creation_edge_kinds(self) -> tuple[str, ...]:
        if self.scope == ALL_REPOSITORIES_SCOPE:
            return _ALL_REPOSITORY_CREATION_EDGE_KINDS
        if self.scope == PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE:
            return _PRIVATE_REPOSITORY_CREATION_EDGE_KINDS
        return ()

    def _read_secret_query(
        self, role_node_id: str, edge_kinds: tuple[str, ...]
    ) -> str:
        creation_edges = "|".join(edge_kinds)
        return (
            f"MATCH p=(:GH_OrgRole {{node_id:'{role_node_id}'}})"
            f"-[:{creation_edges}]->"
            f"(:GH_Organization)-[:GH_Contains]->"
            f"(:GH_Scope {{node_id:'{self.node_id}'}}) RETURN p"
        )

    def _members_can_create_repository_in_scope(
        self, edge_kinds: tuple[str, ...]
    ) -> bool:
        creation_flags = self._lookup.members_can_create_repository(self.org_login)
        if not creation_flags:
            return False

        permissions = dict(zip(_ALL_REPOSITORY_CREATION_EDGE_KINDS, creation_flags))
        return any(bool(permissions.get(edge_kind)) for edge_kind in edge_kinds)

    @property
    def _can_read_secret_edges(self):
        if self.scope_type != ORGANIZATION_SECRET_SCOPE_TYPE:
            return
        if not self._lookup.canonical_scope_has_targets(
            self.org_login, self.scope_type, self.scope
        ):
            return

        edge_kinds = self._repository_creation_edge_kinds
        if not edge_kinds:
            return
        owners_role_id = f"{self.org_node_id}_owners"
        yield Edge(
            kind=ek.CAN_READ_SECRET,
            start=EdgePath(value=owners_role_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=GHEdgeProperties(
                traversable=True,
                composed=True,
                query_composition=self._read_secret_query(
                    owners_role_id, edge_kinds
                ),
            ),
        )

        if self._members_can_create_repository_in_scope(edge_kinds):
            members_role_id = f"{self.org_node_id}_members"
            yield Edge(
                kind=ek.CAN_READ_SECRET,
                start=EdgePath(value=members_role_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    query_composition=self._read_secret_query(
                        members_role_id, edge_kinds
                    ),
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
        yield from self._can_read_secret_edges
