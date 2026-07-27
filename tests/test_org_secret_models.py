from datetime import datetime
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.models.org_role import OrgRole
from openhound_github.models.org_secret import OrgSecret


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


def test_all_visibility_secret_requires_an_actual_member_creation_capability() -> None:
    secret = _secret("all", (False, False, False, False))

    edges = list(secret._composed_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners"]


def test_all_visibility_secret_allows_any_repository_creation_capability() -> None:
    secret = _secret("all", (True, False, False, False))

    edges = list(secret._composed_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners", "O_1_members"]
    assert "GH_CanCreateRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreatePublicRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in edges[1].properties.query_composition
    assert "GH_CanCreatePrivateRepositories" in edges[1].properties.query_composition


def test_private_visibility_secret_only_allows_private_or_internal_creation() -> None:
    secret = _secret("private", (True, True, False, False))

    edges = list(secret._composed_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners"]
    query = edges[0].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in query
    assert "GH_CanCreatePrivateRepositories" in query
    assert "GH_CanCreateRepositories" not in query
    assert "GH_CanCreatePublicRepositories" not in query


def test_private_visibility_secret_allows_internal_repository_creation() -> None:
    secret = _secret("private", (False, False, True, False))

    edges = list(secret._composed_read_secret_edges)

    assert [edge.start.value for edge in edges] == ["O_1_owners", "O_1_members"]


def test_selected_visibility_secret_does_not_emit_latent_read_edges() -> None:
    secret = _secret("selected", (True, True, True, True))

    assert list(secret._composed_read_secret_edges) == []


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
