"""Shared scope selection and edge composition for branch-creation capabilities."""

from collections.abc import Callable, Iterable, Mapping

from openhound.core.models.entries_dataclass import Edge, EdgePath

from openhound_github.graph import GHEdgeProperties
from openhound_github.kinds import edges as ek
from openhound_github.lookup import GithubLookup
from openhound_github.models.scope import (
    REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
    UNRESTRICTED_BRANCH_CREATION_SCOPE,
    scope_node_id,
)


def branch_creation_edges(
    lookup: GithubLookup,
    *,
    credential_node_id: str,
    org_login: str,
    org_node_id: str,
    allow_shared_scope: bool,
    resolve_repositories: Callable[[bool], Iterable[tuple[str, str]]],
    access_query: str,
    repository_evidence_queries: Mapping[str, str],
    supporting_paths: tuple[str, ...] = (),
):
    """Emit capabilities after the caller establishes credential eligibility.

    Shared-scope access requires authority over every scope member, not merely
    all-repository selection. A user-bound credential must establish its owner's
    authority before setting allow_shared_scope. The resolver must independently
    intersect repository access with write authority and protection evidence.
    It receives whether shared members can be omitted from direct edges.
    """
    use_scope = allow_shared_scope and lookup.branch_creation_scope_available(
        org_login, org_node_id
    )
    if use_scope and lookup.canonical_scope_has_targets(
        org_login,
        REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
        UNRESTRICTED_BRANCH_CREATION_SCOPE,
    ):
        target_scope_id = scope_node_id(
            org_node_id,
            REPOSITORY_BRANCH_CREATION_SCOPE_TYPE,
            UNRESTRICTED_BRANCH_CREATION_SCOPE,
        )
        yield Edge(
            kind=ek.CAN_CREATE_BRANCH,
            start=EdgePath(value=credential_node_id, match_by="id"),
            end=EdgePath(value=target_scope_id, match_by="id"),
            properties=GHEdgeProperties(
                traversable=True,
                composed=True,
                reason="contents_write_and_all_repository_access",
                query_composition=(
                    access_query
                    + f"MATCH p1=(:GH_Scope {{node_id:'{target_scope_id}'}})"
                    "-[:GH_ScopedTo]->(repository) RETURN "
                    + ", ".join(("p", "p1", *supporting_paths))
                ),
            ),
        )
    for repository_id, reason in resolve_repositories(use_scope):
        query = (
            access_query
            + f"AND repository.node_id = '{repository_id}' "
            + repository_evidence_queries.get(
                reason, "RETURN " + ", ".join(("p", *supporting_paths))
            )
        )
        yield Edge(
            kind=ek.CAN_CREATE_BRANCH,
            start=EdgePath(value=credential_node_id, match_by="id"),
            end=EdgePath(value=repository_id, match_by="id"),
            properties=GHEdgeProperties(
                traversable=True,
                composed=True,
                reason=reason,
                query_composition=query,
            ),
        )
