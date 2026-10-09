from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.repository_variable import RepoVariable
from openhound_github.models.org_variable import OrgVariable, SelectedOrgVariable
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    ORGANIZATION_VARIABLE_SCOPE_TYPE,
    PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    scope_node_id,
)


def test_repository_variable_access_edge_is_traversable() -> None:
    variable = RepoVariable(
        name="DEPLOY_TARGET",
        value="prod",
        created_at=datetime.now(),
        org_login="acme",
        repository_name="repo",
        repository_node_id="R_1",
    )

    edge = next(edge for edge in variable.edges if edge.kind == ek.HAS_VARIABLE)

    assert edge.properties.traversable is True


def test_canonical_org_variable_visibility_uses_target_scope() -> None:
    all_variable = OrgVariable(
        name="DEPLOY_TARGET",
        value="prod",
        created_at=datetime.now(),
        visibility="all",
        org_login="acme",
    )
    private_variable = OrgVariable(
        name="PRIVATE_TARGET",
        value="private",
        created_at=datetime.now(),
        visibility="private",
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    all_variable._lookup = lookup
    private_variable._lookup = lookup

    all_edge = next(iter(all_variable._all_repo_edges))
    private_edge = next(iter(private_variable._private_repo_edges))

    assert all_edge.kind == ek.SCOPED_TO
    assert all_edge.start.value == scope_node_id(
        "O_1", ORGANIZATION_VARIABLE_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE
    )
    assert private_edge.start.value == scope_node_id(
        "O_1",
        ORGANIZATION_VARIABLE_SCOPE_TYPE,
        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    )
    assert all_edge.properties.traversable is True
    lookup.repository_node_ids_for_org.assert_not_called()
    lookup.private_repository_node_ids_for_org.assert_not_called()


def test_selected_org_variable_remains_direct() -> None:
    selected = SelectedOrgVariable(
        name="DEPLOY_TARGET", repository_node_id="R_1", org_login="acme"
    )
    selected._lookup = MagicMock(org_id_for_login=lambda _login: "O_1")

    edges = list(selected.edges)

    assert [edge.kind for edge in edges] == [ek.HAS_VARIABLE]
    assert edges[0].start.value == "R_1"
