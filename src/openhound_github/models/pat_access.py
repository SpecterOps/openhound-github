"""Non-traversable access-scope metadata shared by PATs and pending requests."""

from openhound.core.models.entries_dataclass import Edge, EdgePath, EdgeProperties

from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    REPOSITORY_SCOPE_TYPE,
    scope_node_id,
)


def pat_access_edges(
    lookup: GithubLookup,
    *,
    node_id: str,
    org_node_id: str | None,
    repository_selection: str | None,
    permissions: dict[str, list[str]],
):
    """Declared scope is metadata; a pending request does not confer authority."""
    if not org_node_id:
        return
    targets = []
    if permissions["permissions_organization"]:
        targets.append(org_node_id)
    if permissions["permissions_enterprise"]:
        enterprise_id = lookup.enterprise_id_for_organization(org_node_id)
        if enterprise_id:
            targets.append(enterprise_id)
    if repository_selection == "all":
        targets.append(
            scope_node_id(org_node_id, REPOSITORY_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE)
        )
    for target in targets:
        yield Edge(
            kind=ek.CAN_ACCESS,
            start=EdgePath(value=node_id, match_by="id"),
            end=EdgePath(value=target, match_by="id"),
            properties=EdgeProperties(traversable=False),
        )
