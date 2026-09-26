import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.models.app_installation import AppInstallation
from openhound_github.models.personal_access_token import (
    Owner as PersonalAccessTokenOwner,
    Permissions,
    PersonalAccessToken,
)
from openhound_github.models.personal_access_token_request import (
    Owner as PersonalAccessTokenRequestOwner,
    PersonalAccessTokenRequest,
)
from openhound_github.models.repository import Owner as RepositoryOwner
from openhound_github.models.repository import Repository
from openhound_github.models.scope import (
    ALL_REPOSITORIES_SCOPE,
    PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    REPOSITORY_SCOPE_TYPE,
    RUNNER_GROUP_SCOPE_TYPE,
    Scope,
    scope_node_id,
)


ORG_NODE_ID = "O_1"
SCOPE_NODE_ID = scope_node_id(
    ORG_NODE_ID, REPOSITORY_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE
)


def _lookup() -> MagicMock:
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = ORG_NODE_ID
    lookup.repository_graphql_counts.return_value = (None, None, None)
    lookup.repository_workflow_permissions.return_value = None
    lookup.canonical_scope_target_count.return_value = 4
    return lookup


def _installation(installation_id: int, selection: str = "all") -> AppInstallation:
    installation = AppInstallation(
        id=installation_id,
        repository_selection=selection,
        app_id=42,
        target_type="Organization",
        permissions={"contents": "read"},
        created_at=datetime(2026, 1, 1),
        org_login="acme",
    )
    installation._lookup = _lookup()
    return installation


def _pat(selection: str) -> PersonalAccessToken:
    token = PersonalAccessToken(
        id=1,
        owner=PersonalAccessTokenOwner(
            login="octocat",
            id=1,
            type="User",
            node_id="U_1",
        ),
        repository_selection=selection,
        permissions=Permissions(repository={"contents": "read"}),
        token_id=1,
        token_name="automation",
        token_expired=False,
        org_login="acme",
    )
    token._lookup = _lookup()
    return token


def _repository(repo_number: int, visibility: str | None = None) -> Repository:
    repository = Repository(
        id=repo_number,
        node_id=f"R_{repo_number}",
        name=f"repo-{repo_number}",
        full_name=f"acme/repo-{repo_number}",
        private=True,
        owner=RepositoryOwner(
            login="acme",
            id=1,
            node_id=ORG_NODE_ID,
            avatar_url="",
            gravatar_id="",
            url="",
            html_url="",
            followers_url="",
            following_url="",
            gists_url="",
            starred_url="",
            subscriptions_url="",
            organizations_url="",
            repos_url="",
            events_url="",
            received_events_url="",
            type="Organization",
            site_admin=False,
        ),
        org_login="acme",
        visibility=visibility,
    )
    repository._lookup = _lookup()
    return repository


def _pat_request(selection: str) -> PersonalAccessTokenRequest:
    request = PersonalAccessTokenRequest(
        id=2,
        owner=PersonalAccessTokenRequestOwner(
            login="octocat", id=1, type="User", node_id="U_1", site_admin=False
        ),
        repository_selection=selection,
        token_name="requested automation",
        token_expired=False,
        org_login="acme",
    )
    request._lookup = _lookup()
    return request


def test_all_repository_scope_is_stable_and_organization_scoped() -> None:
    scope = Scope(
        org_node_id=ORG_NODE_ID,
        org_login="acme",
        scope_type=REPOSITORY_SCOPE_TYPE,
        scope=ALL_REPOSITORIES_SCOPE,
    )
    scope._lookup = _lookup()

    assert scope.node_id == SCOPE_NODE_ID
    assert scope.as_node.kinds == [nk.SCOPE, "GitHub"]
    assert scope.as_node.properties.scope_type == REPOSITORY_SCOPE_TYPE
    assert scope.as_node.properties.member_count == 4
    assert scope.as_node.properties.scope == "all"
    assert scope.as_node.properties.displayname == "acme/repository/all"
    edge = next(iter(scope.edges))
    assert edge.kind == ek.CONTAINS
    assert edge.start.value == ORG_NODE_ID
    assert edge.end.value == SCOPE_NODE_ID
    assert edge.properties.traversable is False


def test_all_installations_and_pat_share_scope_without_repository_fanout() -> None:
    access_edges = []
    for installation_id in range(1, 4):
        installation = _installation(installation_id)
        edges = list(installation.edges)
        access_edges.extend(edge for edge in edges if edge.kind == ek.CAN_ACCESS)
        installation._lookup.repository_node_ids_for_org.assert_not_called()

    pat_edges = list(_pat("all").edges)
    pat_repository_access = [
        edge
        for edge in pat_edges
        if edge.kind == ek.CAN_ACCESS and edge.end.value == SCOPE_NODE_ID
    ]

    assert len(access_edges) == 3
    assert {edge.end.value for edge in access_edges} == {SCOPE_NODE_ID}
    assert len(pat_repository_access) == 1
    assert all(edge.properties.traversable is False for edge in access_edges)


def test_repository_scope_reduces_shared_policy_edges_to_sources_plus_repositories() -> None:
    all_access_edges = [
        edge
        for installation_id in range(1, 4)
        for edge in _installation(installation_id).edges
        if edge.kind == ek.CAN_ACCESS
    ]
    scoped_to_edges = [
        edge
        for repo_number in range(1, 5)
        for edge in _repository(repo_number).edges
        if edge.kind == ek.SCOPED_TO
    ]

    assert len(all_access_edges) + len(scoped_to_edges) == 3 + 4
    assert {edge.start.value for edge in scoped_to_edges} == {SCOPE_NODE_ID}
    assert all(edge.properties.traversable is True for edge in scoped_to_edges)


def test_private_or_internal_scope_contains_only_non_public_repositories() -> None:
    private_scope_id = scope_node_id(
        ORG_NODE_ID,
        REPOSITORY_SCOPE_TYPE,
        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    )
    scoped_edges = [
        edge
        for repo_number, visibility in enumerate(("public", "private", "internal"), 1)
        for edge in _repository(repo_number, visibility).edges
        if edge.kind == ek.SCOPED_TO and edge.start.value == private_scope_id
    ]

    assert {edge.end.value for edge in scoped_edges} == {"R_2", "R_3"}


def test_repositories_join_the_matching_runner_group_scopes() -> None:
    all_scope_id = scope_node_id(
        ORG_NODE_ID, RUNNER_GROUP_SCOPE_TYPE, ALL_REPOSITORIES_SCOPE
    )
    private_scope_id = scope_node_id(
        ORG_NODE_ID,
        RUNNER_GROUP_SCOPE_TYPE,
        PRIVATE_OR_INTERNAL_REPOSITORIES_SCOPE,
    )
    eligible_targets = {
        edge.end.value
        for edge in _repository(1, "private").edges
        if edge.kind == ek.IS_ELIGIBLE_FOR
    }

    assert eligible_targets == {all_scope_id, private_scope_id}


def test_repository_does_not_join_empty_target_scopes() -> None:
    repository = _repository(1, "private")
    repository._lookup.canonical_scope_has_targets.return_value = False

    boundary_kinds = {ek.IS_ELIGIBLE_FOR, ek.HAS_SECRET, ek.HAS_VARIABLE}

    assert not [edge for edge in repository.edges if edge.kind in boundary_kinds]


def test_arbitrary_selections_do_not_use_repository_scope() -> None:
    assert ek.CAN_ACCESS not in {edge.kind for edge in _installation(1, "selected").edges}
    pat_access_targets = {
        edge.end.value for edge in _pat("subset").edges if edge.kind == ek.CAN_ACCESS
    }

    assert SCOPE_NODE_ID not in pat_access_targets


def test_all_pat_request_uses_pending_access_edge_without_granting_access() -> None:
    all_request = _pat_request("all")
    access_edges = [
        edge
        for edge in all_request.edges
        if edge.kind in {ek.REQUESTS_ACCESS_TO, ek.CAN_ACCESS}
    ]

    assert [(edge.kind, edge.end.value) for edge in access_edges] == [
        (ek.REQUESTS_ACCESS_TO, SCOPE_NODE_ID)
    ]
    assert access_edges[0].properties.traversable is False
    assert ek.REQUESTS_ACCESS_TO not in {
        edge.kind for edge in _pat_request("subset").edges
    }


def test_credential_repository_queries_support_direct_and_scoped_access() -> None:
    expected_pattern = "[:GH_CanAccess|GH_ScopedTo*1..2]->(:GH_Repository)"

    assert expected_pattern in _installation(1).as_node.properties.query_repositories
    assert expected_pattern in _pat("all").as_node.properties.query_repositories


def test_schema_registers_repository_scope_and_compatible_panel_queries() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "extension" / "schema.json"
    schema = json.loads(schema_path.read_text())
    node_names = {node["name"] for node in schema["node_kinds"]}
    relationship_kinds = {
        relationship["name"]: relationship
        for relationship in schema["relationship_kinds"]
    }

    assert nk.SCOPE in node_names
    assert relationship_kinds[ek.SCOPED_TO]["is_traversable"] is True
    assert relationship_kinds[ek.REQUESTS_ACCESS_TO]["is_traversable"] is False

    schema_text = schema_path.read_text()
    assert "GH_CanAccess|GH_ScopedTo*1..2" in schema_text
    assert "GH_InstalledAs|GH_CanAccess|GH_ScopedTo*2..3" in schema_text
    assert "GH_RequestsAccessTo|GH_ScopedTo*1..2" in schema_text
    assert "GH_IsEligibleFor|GH_ScopedTo*1..2" in schema_text
    assert "GH_HasSecret|GH_ScopedTo*1..2" in schema_text
    assert "GH_HasVariable|GH_ScopedTo*1..2" in schema_text


def test_secret_entity_panel_resolves_direct_and_scoped_relationships() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "extension" / "schema.json"
    schema = json.loads(schema_path.read_text())
    secret = next(node for node in schema["node_kinds"] if node["name"] == nk.SECRET)
    inbound_query = secret["info"]["inbound_traversable_relationships"]["markdown"][
        "content"
    ]

    assert (
        "GH_HasSecret|GH_CanReadSecret|GH_CanAccessSecret|GH_ScopedTo*1..2"
        in inbound_query
    )


def test_secret_saved_searches_resolve_direct_and_scoped_secrets() -> None:
    saved_searches = Path(__file__).resolve().parents[1] / "extension" / "saved_searches"

    for name in (
        "repos-vulnerable-to-workflow-secret-exfil.json",
        "secrets-reachable-by-user.json",
    ):
        query = json.loads((saved_searches / name).read_text())["query"]
        assert "GH_HasSecret|GH_ScopedTo*1..2" in query
