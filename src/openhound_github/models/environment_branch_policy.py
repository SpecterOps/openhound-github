from dataclasses import dataclass
from pathlib import PurePosixPath

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app

# from openhound_github.helpers import _b64

@dataclass
class GHEnvironmentBranchPolicyProperties(GHNodeProperties):
    environment_name: str | None = None
    repository_name: str | None = None

@app.asset(
    node=NodeDef(
        kind=nk.ENVIRONMENT_BRANCH_POLICY,
        description="GitHub environment deployment branch policy",
        icon="code-branch",
        properties=GHEnvironmentBranchPolicyProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ENVIRONMENT,
            end=nk.ENVIRONMENT_BRANCH_POLICY,
            kind=ek.CONTAINS,
            description="Environment contains deployment branch policy",
            traversable=False,
        ),
        EdgeDef(
            start=nk.BRANCH,
            end=nk.ENVIRONMENT_BRANCH_POLICY,
            kind=ek.MATCHES_ENVIRONMENT_POLICY,
            description="Branch matches environment deployment policy",
            traversable=False,
        ),
    ],
)
class EnvironmentBranchPolicy(BaseAsset):
    """One record from `environment_branch_policies` → GH_Contains edge from synthetic policy ID. No node."""

    id: int
    node_id: str
    name: str

    environment_node_id: str
    environment_name: str
    repository_name: str
    repository_node_id: str
    org_login: str

    @property
    def org_node_id(self) -> str | None:
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def policy_id(self) -> str:
        # return _b64(f"{self.environment_node_id}_{self.name}")
        return f"{self.environment_node_id}_{self.name}"

    @property
    def environment_protected_branches(self) -> bool:
        row = self._lookup.environment_deployment_branch_policy(
            self.environment_name, self.repository_node_id
        )
        if not row:
            return False
        protected_branches, _custom_branch_policies = row
        return protected_branches

    def matches_branch(self, branch_name: str) -> bool:
        return PurePosixPath(f"/{branch_name}").full_match(
            f"/{self.name}",
            case_sensitive=True,
        )

    @property
    def as_node(self) -> GHNode:
        return GHNode(
            kinds=[nk.ENVIRONMENT_BRANCH_POLICY],
            properties=GHEnvironmentBranchPolicyProperties(
                name=self.name,
                displayname=self.name,
                node_id=self.node_id,
                environment_name=self.environment_name,
                repository_name=self.repository_name,
                environmentid=self.environment_node_id,
            ),
        )

    def _policy_branch_can_deploy_query(self, branch_id: str) -> str:
        return (
            f"MATCH p=(:GH_Branch {{node_id:'{branch_id}'}})"
            f"-[:GH_MatchesEnvironmentPolicy]->"
            f"(:GH_EnvironmentBranchPolicy {{node_id:'{self.node_id}'}})"
            f"<-[:GH_Contains]-(env:GH_Environment {{node_id:'{self.environment_node_id}'}}) "
            f"WHERE env.custom_branch_policies = true "
            f"AND coalesce(env.protected_branches, false) = false "
            f"RETURN p"
        )

    def _protected_policy_branch_can_deploy_query(self, branch_id: str) -> str:
        return (
            f"MATCH p=(:GH_Branch {{node_id:'{branch_id}'}})"
            f"-[:GH_MatchesEnvironmentPolicy]->"
            f"(:GH_EnvironmentBranchPolicy {{node_id:'{self.node_id}'}})"
            f"<-[:GH_Contains]-(env:GH_Environment {{node_id:'{self.environment_node_id}'}}) "
            f"MATCH p1=(repo:GH_Repository {{node_id:'{self.repository_node_id}'}})"
            f"-[:GH_Contains]->(:GH_Branch {{node_id:'{branch_id}'}})"
            f"<-[:GH_ProtectedBy]-(:GH_BranchProtectionRule) "
            f"MATCH p2=(repo)-[:GH_Contains]->(env) "
            f"WHERE env.custom_branch_policies = true "
            f"AND env.protected_branches = true "
            f"RETURN p, p1, p2"
        )

    @property
    def edges(self):
        yield Edge(
            kind=ek.CONTAINS,
            start=EdgePath(value=self.environment_node_id, match_by="id"),
            end=EdgePath(value=self.node_id, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
        branches = self._lookup.branches_for_repository(self.repository_node_id)
        for branch_id, branch_name, protected in branches:
            if self.matches_branch(branch_name):
                yield Edge(
                    kind=ek.MATCHES_ENVIRONMENT_POLICY,
                    start=EdgePath(value=branch_id, match_by="id"),
                    end=EdgePath(value=self.node_id, match_by="id"),
                    properties=EdgeProperties(traversable=False),
                )
                if not self.environment_protected_branches or protected:
                    yield Edge(
                        kind=ek.CAN_DEPLOY_TO_ENVIRONMENT,
                        start=EdgePath(value=branch_id, match_by="id"),
                        end=EdgePath(value=self.environment_node_id, match_by="id"),
                        properties=GHEdgeProperties(
                            traversable=True,
                            composed=True,
                            query_composition=(
                                self._protected_policy_branch_can_deploy_query(branch_id)
                                if self.environment_protected_branches
                                else self._policy_branch_can_deploy_query(branch_id)
                            ),
                        ),
                    )
