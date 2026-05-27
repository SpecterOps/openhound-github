from dataclasses import dataclass
from datetime import datetime

from openhound.core.asset import BaseAsset, EdgeDef, NodeDef
from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties
from pydantic import BaseModel

from openhound_github.graph import GHEdgeProperties, GHNode, GHNodeProperties
from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app


class Owner(BaseModel):
    login: str
    id: int
    node_id: str
    type: str


class ResolvedBy(BaseModel):
    login: str
    id: int
    node_id: str
    type: str


class Repository(BaseModel):
    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: Owner | None = None


@dataclass
class GHSecretScanningAlertProperties(GHNodeProperties):
    """Secret scanning alert properties and accordion panel queries.

    Attributes:
        repository_name: The name of the repository where the secret was detected.
        secret_type: The type of secret detected (e.g., `github_personal_access_token`, `aws_access_key_id`).
        secret_type_display_name: A human-readable name for the secret type.
        validity: The validity status of the detected secret (e.g., `active`, `inactive`, `unknown`).
        state: The alert state (e.g., `open`, `resolved`).
        url: The HTML URL to view the alert on GitHub.
        query_repository: Query for repository.
        query_alert_viewers: Query for alert viewers.
    """

    # TODO: Check the following fields
    # repository_id, repository_url, created_at, updated_at

    repository_name: str | None = None
    secret_type: str | None = None
    secret_type_display_name: str | None = None
    validity: str | None = None
    state: str | None = None
    url: str | None = None
    query_repository: str | None = None
    query_alert_viewers: str | None = None


@app.asset(
    node=NodeDef(
        kind=nk.SECRET_SCANNING_ALERT,
        description="GitHub Secret Scanning Alert",
        icon="key",
        properties=GHSecretScanningAlertProperties,
    ),
    edges=[
        EdgeDef(
            start=nk.ORGANIZATION,
            end=nk.SECRET_SCANNING_ALERT,
            kind=ek.CONTAINS,
            description="Org contains secret scanning alert",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPOSITORY,
            end=nk.SECRET_SCANNING_ALERT,
            kind=ek.CONTAINS,
            description="Repository contains secret scanning alert",
            traversable=False,
        ),
        EdgeDef(
            start=nk.REPO_ROLE,
            end=nk.SECRET_SCANNING_ALERT,
            kind=ek.CAN_READ_SECRET_SCANNING_ALERT,
            description="Repository role can read secret scanning alert",
            traversable=True,
        ),
        EdgeDef(
            start=nk.ORG_ROLE,
            end=nk.SECRET_SCANNING_ALERT,
            kind=ek.CAN_READ_SECRET_SCANNING_ALERT,
            description="Organization role can read secret scanning alert",
            traversable=True,
        ),
        EdgeDef(
            start=nk.SECRET_SCANNING_ALERT,
            end=nk.USER,
            kind=ek.VALID_TOKEN,
            description="Alert secret is a valid PAT for this user",
            traversable=True,
        ),
    ],
)
class SecretScanningAlert(BaseAsset):
    """One record from `secret_scanning_alerts` → one GH_SecretScanningAlert node + edges."""

    number: int
    created_at: datetime
    url: str
    html_url: str
    state: str
    resolution: str | None = None
    resolved_at: datetime | None = None
    resolved_by: ResolvedBy | None = None
    secret_type: str
    secret_type_display_name: str | None = None
    secret: str | None = None
    repository: Repository | None = None
    push_protection_bypassed: bool | None = None
    push_protection_bypassed_by: ResolvedBy | None = None
    push_protection_bypassed_at: datetime | None = None
    resolution_comment: str | None = None
    validity: str | None = None

    # Additional
    org_login: str
    valid_token_user_node_id: str | None = (
        None  # based on lookup of users with valid tokens matching the secret
    )

    @property
    def node_id(self) -> str:
        repo_node_id: str = self.repository.node_id if self.repository else ""
        """ The ID from a GraphQL API response is the same as a regular node_id """
        return f"SSA_{repo_node_id}_{self.number}"

    @property
    def org_node_id(self) -> str | None:
        if self.repository and self.repository.owner:
            return self.repository.owner.node_id
        return self._lookup.org_id_for_login(self.org_login)

    @property
    def as_node(self) -> GHNode:
        aid = self.node_id
        return GHNode(
            kinds=[nk.SECRET_SCANNING_ALERT],
            properties=GHSecretScanningAlertProperties(
                name=str(self.number),
                displayname=self.secret_type_display_name or str(self.number),
                node_id=aid,
                environmentid=self.org_node_id,
                repository_name=self.repository.name if self.repository else "",
                secret_type=self.secret_type,
                secret_type_display_name=self.secret_type_display_name,
                validity=self.validity,
                state=self.state,
                url=self.url,
                query_repository=f"MATCH p=(r:GH_SecretScanningAlert {{node_id:'{aid}'}})<-[:GH_Contains]-(repo:GH_Repository) RETURN p",
                query_alert_viewers=(
                    f"MATCH p=(role:GH_Role)-[:GH_HasRole|GH_HasBaseRole|GH_MemberOf|GH_CanReadSecretScanningAlert*1..]->"
                    f"(:GH_SecretScanningAlert {{node_id:'{aid}'}}) "
                    f"MATCH p1=(role)<-[:GH_HasRole]-(:GH_User) RETURN p,p1"
                ),
            ),
        )

    def _repo_alert_view_query(self, role_node_id: str) -> str:
        return (
            f"MATCH p=(:GH_RepoRole {{node_id:'{role_node_id}'}})"
            f"-[:GH_ViewSecretScanningAlerts]->(:GH_Repository)"
            f"-[:GH_Contains]->(:GH_SecretScanningAlert {{node_id:'{self.node_id}'}}) "
            f"RETURN p"
        )

    def _org_alert_view_query(self, role_node_id: str) -> str:
        return (
            f"MATCH p=(:GH_OrgRole {{node_id:'{role_node_id}'}})"
            f"-[:GH_ViewSecretScanningAlerts]->(:GH_Organization)"
            f"-[:GH_Contains]->(:GH_SecretScanningAlert {{node_id:'{self.node_id}'}}) "
            f"RETURN p"
        )

    @property
    def _repo_viewer_edges(self):
        if not self.repository:
            return

        for (role_node_id,) in self._lookup.repo_role_node_ids_with_view_secret_scanning_alerts(
            self.repository.node_id
        ):
            yield Edge(
                kind=ek.CAN_READ_SECRET_SCANNING_ALERT,
                start=EdgePath(value=role_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    query_composition=self._repo_alert_view_query(role_node_id),
                ),
            )

    @property
    def _org_viewer_edges(self):
        if not self.org_node_id:
            return

        for (role_node_id,) in self._lookup.org_role_node_ids_with_view_secret_scanning_alerts(
            self.org_login
        ):
            yield Edge(
                kind=ek.CAN_READ_SECRET_SCANNING_ALERT,
                start=EdgePath(value=role_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=GHEdgeProperties(
                    traversable=True,
                    composed=True,
                    query_composition=self._org_alert_view_query(role_node_id),
                ),
            )

    @property
    def edges(self):
        if self.repository:
            yield Edge(
                kind=ek.CONTAINS,
                start=EdgePath(value=self.repository.node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )
        if self.org_node_id:
            yield Edge(
                kind=ek.CONTAINS,
                start=EdgePath(value=self.org_node_id, match_by="id"),
                end=EdgePath(value=self.node_id, match_by="id"),
                properties=EdgeProperties(traversable=False),
            )

        if self.valid_token_user_node_id:
            yield Edge(
                kind=ek.VALID_TOKEN,
                start=EdgePath(value=self.node_id, match_by="id"),
                end=EdgePath(value=self.valid_token_user_node_id, match_by="id"),
                properties=EdgeProperties(traversable=True),
            )

        yield from self._repo_viewer_edges
        yield from self._org_viewer_edges
