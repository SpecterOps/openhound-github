from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.org_role import OrgRole
from openhound_github.models.org_secret import OrgSecret
from openhound_github.models.org_secret import SelectedOrgSecret
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    ORGANIZATION_SECRET_SCOPE_TYPE,
    PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    Scope,
    scope_node_id,
)


def _secret(
    visibility: str,
    creation_flags: tuple[bool, bool, bool, bool],
) -> OrgSecret:
    secret = OrgSecret(
        name="DEPLOY_TOKEN",
        created_at=datetime.now(),
        visibility=visibility,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.members_can_create_repository.return_value = creation_flags
    secret._lookup = lookup
    return secret


def _secret_scope(
    scope: str,
    creation_flags: tuple[bool, bool, bool, bool],
    target_count: int = 1,
) -> Scope:
    secret_scope = Scope(
        org_node_id="O_1",
        org_login="acme",
        scope_type=ORGANIZATION_SECRET_SCOPE_TYPE,
        scope=scope,
    )
    lookup = MagicMock()
    lookup.canonical_scope_has_targets.return_value = target_count > 0
    lookup.members_can_create_repository.return_value = creation_flags
    secret_scope._lookup = lookup
    return secret_scope


def test_all_secret_scope_requires_an_actual_member_creation_capability() -> None:
    scope = _secret_scope(ALL_REPOSITORIES_SCOPE, (False, False, False, False))

    edges = list(scope._can_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners"]
    assert edges[0].end.value == scope.node_id
    assert scope.node_id in edges[0].properties.query_composition
    assert ":GH_Scope" in edges[0].properties.query_composition


def test_all_secret_scope_allows_any_repository_creation_capability() -> None:
    scope = _secret_scope(ALL_REPOSITORIES_SCOPE, (True, False, False, False))

    edges = list(scope._can_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners", "O_1_members"]
    assert "GH_CanCreateRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreatePublicRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreatePrivateRepositories" in edges[1].properties.query_composition


def test_private_secret_scope_only_allows_private_or_internal_creation() -> None:
    scope = _secret_scope(
        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE, (True, True, False, False)
    )

    edges = list(scope._can_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners"]
    query = edges[0].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in query
    assert "GH_CanCreatePrivateRepositories" in query
    assert "GH_CanCreateRepositories" not in query
    assert "GH_CanCreatePublicRepositories" not in query


def test_private_secret_scope_allows_internal_repository_creation() -> None:
    scope = _secret_scope(
        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE, (False, False, True, False)
    )

    edges = list(scope._can_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners", "O_1_members"]


def test_empty_secret_scope_does_not_emit_latent_read_edges() -> None:
    scope = _secret_scope(ALL_REPOSITORIES_SCOPE, (True, True, True, True), 0)

    assert list(scope._can_read_secret_edges) == []


def test_canonical_secret_visibility_uses_target_scope_without_repository_fanout() -> None:
    all_secret = _secret("all", (False, False, False, False))
    private_secret = _secret("private", (False, False, False, False))

    all_edge = next(iter(all_secret._all_repo_edges))
    private_edge = next(iter(private_secret._private_repo_edges))

    assert all_edge.kind == ek.SCOPED_TO
    assert all_edge.start.value == scope_node_id(
        "O_1", ORGANIZATION_SECRET_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE
    )
    assert private_edge.start.value == scope_node_id(
        "O_1", ORGANIZATION_SECRET_SCOPE_TYPE, PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE
    )
    assert all_edge.end.value == all_secret.node_id
    assert all_edge.properties.traversable is True
    all_secret._lookup.repository_node_ids_for_org.assert_not_called()
    private_secret._lookup.private_repository_node_ids_for_org.assert_not_called()


def test_selected_secret_keeps_direct_relationship_without_repeated_containment() -> None:
    selected = SelectedOrgSecret(
        name="DEPLOY_TOKEN",
        repository_node_id="R_1",
        repository_full_name="acme/repo",
        org_login="acme",
    )
    selected._lookup = MagicMock(org_id_for_login=lambda _login: "O_1")

    edges = list(selected.edges)

    assert [edge.kind for edge in edges] == [ek.HAS_SECRET]
    assert edges[0].start.value == "R_1"
    assert edges[0].properties.traversable is True


def test_owners_always_emit_repository_creation_edges_needed_for_secret_paths() -> None:
    role = OrgRole(
        id=1,
        name="owners",
        type="default",
        base_role="admin",
        created_at=datetime.now(),
        org_node_id="O_1",
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.members_can_create_repository.return_value = (False, False, False, False)
    role._lookup = lookup

    kinds = {edge.kind for edge in role._can_create_repos_edge}

    assert ek.CAN_CREATE_REPOSITORIES in kinds
    assert ek.CAN_CREATE_PUBLIC_REPOSITORIES in kinds
    assert ek.CAN_CREATE_PRIVATE_REPOSITORIES in kinds


def test_custom_org_role_write_definition_edge_is_traversable() -> None:
    role = OrgRole(
        id=2,
        name="security-manager",
        type="custom",
        permissions=["write_organization_custom_org_role"],
        created_at=datetime.now(),
        org_node_id="O_1",
        org_login="acme",
    )
    role._lookup = MagicMock()

    edge = next(
        edge
        for edge in role.edges
        if edge.kind == "GH_WriteOrganizationCustomOrgRole"
    )

    assert edge.properties.traversable is True
