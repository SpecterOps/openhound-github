import duckdb
from types import SimpleNamespace
from unittest.mock import MagicMock

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.lookup import GithubLookup
from openhound_github.models.runner import (
    EnterpriseRunner,
    EnterpriseRunnerGroup,
    EnterpriseRunnerGroupMembership,
    EnterpriseRunnerGroupOrganization,
    OrgRunner,
    OrgRunnerGroup,
    OrgRunnerGroupAccess,
    OrgRunnerGroupMembership,
    RepoRunner,
)


def test_org_runner_group_keeps_generic_runner_group_label() -> None:
    group = OrgRunnerGroup(id=1, name="Default", org_login="acme")
    group._lookup = SimpleNamespace(org_id_for_login=lambda _login: "ORG_1")

    node = group.as_node

    assert node.kinds == [nk.ORG_RUNNER_GROUP, nk.RUNNER_GROUP]
    assert node.properties.scope == "organization"
    assert node.id == "ORG_1_runner_group_1"


def test_inherited_org_runner_group_emits_inherited_from_edge() -> None:
    group = OrgRunnerGroup(id=1, name="Default", inherited=True, org_login="acme")
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.enterprise_runner_group_node_id_for_inherited_org_group.return_value = (
        "ENT_1_runner_group_2"
    )
    group._lookup = lookup

    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS, ek.INHERITED_FROM]
    assert edges[1].start.value == "ORG_1_runner_group_1"
    assert edges[1].end.value == "ENT_1_runner_group_2"
    assert edges[1].properties.traversable is True
    lookup.enterprise_runner_group_node_id_for_inherited_org_group.assert_called_once_with(
        "ORG_1", "Default"
    )


def test_non_inherited_org_runner_group_does_not_resolve_enterprise_group() -> None:
    group = OrgRunnerGroup(id=1, name="Default", inherited=False, org_login="acme")
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    group._lookup = lookup

    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS]
    lookup.enterprise_runner_group_node_id_for_inherited_org_group.assert_not_called()


def test_inherited_org_runner_group_uses_enterprise_runner_query() -> None:
    group = OrgRunnerGroup(id=1, name="Default", inherited=True, org_login="acme")
    group._lookup = SimpleNamespace(org_id_for_login=lambda _login: "ORG_1")

    assert "GH_InheritedFrom" in group.as_node.properties.query_runners
    assert "GH_EnterpriseRunner" in group.as_node.properties.query_runners


def test_runner_groups_and_runners_use_scope_owner_prefixes_with_generic_suffixes() -> None:
    org_runner = OrgRunner(id=8, name="org-runner-1", org_login="acme")
    org_runner._lookup = SimpleNamespace(org_id_for_login=lambda _login: "ORG_1")
    group = EnterpriseRunnerGroup(
        id=2,
        name="Enterprise Default",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    runner = EnterpriseRunner(
        id=9,
        name="enterprise-runner-1",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    repo_runner = RepoRunner(
        id=10,
        name="repo-runner-1",
        repository_name="repo",
        repository_node_id="REPO_1",
        repository_full_name="acme/repo",
        org_login="acme",
    )
    repo_runner._lookup = SimpleNamespace(org_id_for_login=lambda _login: "ORG_1")

    assert org_runner.as_node.kinds == [nk.ORG_RUNNER, nk.RUNNER]
    assert org_runner.as_node.properties.scope == "organization"
    assert org_runner.as_node.id == "ORG_1_runner_8"
    assert org_runner.as_node.properties.name == "acme/org-runner-1"
    assert org_runner.as_node.properties.displayname == "org-runner-1"
    assert group.as_node.kinds == [nk.ENTERPRISE_RUNNER_GROUP, nk.RUNNER_GROUP]
    assert group.as_node.properties.scope == "enterprise"
    assert group.as_node.id == "ENT_1_runner_group_2"

    assert runner.as_node.kinds == [nk.ENTERPRISE_RUNNER, nk.RUNNER]
    assert runner.as_node.properties.scope == "enterprise"
    assert runner.as_node.id == "ENT_1_runner_9"
    assert runner.as_node.properties.name == "acme-enterprise/enterprise-runner-1"
    assert runner.as_node.properties.displayname == "enterprise-runner-1"

    assert repo_runner.as_node.kinds == [nk.REPO_RUNNER, nk.RUNNER]
    assert repo_runner.as_node.properties.scope == "repository"
    assert repo_runner.as_node.id == "REPO_1_runner_10"
    assert repo_runner.as_node.properties.name == "acme/repo/repo-runner-1"
    assert repo_runner.as_node.properties.displayname == "repo-runner-1"


def test_enterprise_runner_group_with_all_visibility_emits_only_containment() -> None:
    group = EnterpriseRunnerGroup(
        id=2,
        name="Enterprise Default",
        visibility="all",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS]


def test_enterprise_runner_group_with_selected_visibility_does_not_infer_orgs() -> None:
    group = EnterpriseRunnerGroup(
        id=2,
        name="Selected Group",
        visibility="selected",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS]


def test_enterprise_runner_group_membership_contains_enterprise_runner() -> None:
    membership = EnterpriseRunnerGroupMembership(
        runner_group_id=2,
        runner_id=9,
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )

    edges = list(membership.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS, ek.HAS_RUNNER]
    assert all(edge.start.value == "ENT_1_runner_group_2" for edge in edges)
    assert all(edge.end.value == "ENT_1_runner_9" for edge in edges)
    assert edges[0].properties.traversable is False
    assert edges[1].properties.traversable is True


def test_enterprise_runner_group_organization_emits_no_graph_edge() -> None:
    assignment = EnterpriseRunnerGroupOrganization(
        node_id="ORG_1",
        login="acme-org",
        runner_group_id=2,
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )

    assert list(assignment.edges) == []


def test_org_runner_group_access_emits_repository_access_to_inherited_group() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        inherited=True,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.repository_node_ids_for_org.return_value = [("REPO_1",)]
    lookup.members_can_create_repository.return_value = (False, False, False, False)
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [ek.IS_ELIGIBLE_FOR]
    assert edges[0].start.value == "REPO_1"
    assert edges[0].end.value == "ORG_1_runner_group_1"
    assert edges[0].properties.traversable is False


def test_org_runner_group_access_all_visibility_excludes_public_repositories_when_disabled() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        allows_public_repositories=False,
        inherited=True,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.private_repository_node_ids_for_org.return_value = [("REPO_PRIVATE",)]
    lookup.members_can_create_repository.return_value = (False, False, False, False)
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [ek.IS_ELIGIBLE_FOR]
    assert edges[0].start.value == "REPO_PRIVATE"
    assert edges[0].end.value == "ORG_1_runner_group_1"
    lookup.private_repository_node_ids_for_org.assert_called_with("acme")
    lookup.repository_node_ids_for_org.assert_not_called()


def test_org_runner_group_access_selected_visibility_excludes_public_repositories_when_disabled() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Selected",
        runner_group_visibility="selected",
        allows_public_repositories=False,
        accessible_repo_node_ids=["REPO_PRIVATE", "REPO_PUBLIC"],
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.private_repository_node_ids_for_org.return_value = [("REPO_PRIVATE",)]
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [ek.IS_ELIGIBLE_FOR]
    lookup.branch_node_ids_for_org.assert_not_called()
    assert edges[0].start.value == "REPO_PRIVATE"
    assert edges[0].end.value == "ORG_1_runner_group_1"


def test_org_runner_group_access_emits_traversable_use_edges_for_unrestricted_group() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Selected",
        runner_group_visibility="selected",
        restricted_to_workflows=False,
        accessible_repo_node_ids=["REPO_1"],
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.actions_enabled_repository_node_ids_for_org.return_value = [("REPO_1",)]
    lookup.branch_node_ids_for_org.return_value = [
        ("REPO_1", "BRANCH_1"),
        ("REPO_2", "BRANCH_2"),
    ]
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.IS_ELIGIBLE_FOR,
        ek.CAN_USE_RUNNER,
        ek.CAN_USE_RUNNER,
    ]
    assert [(edge.start.value, edge.end.value) for edge in edges] == [
        ("REPO_1", "ORG_1_runner_group_1"),
        ("REPO_1", "ORG_1_runner_group_1"),
        ("BRANCH_1", "ORG_1_runner_group_1"),
    ]
    assert edges[0].properties.traversable is False
    assert all(edge.properties.traversable is True for edge in edges[1:])


def test_org_runner_group_access_does_not_emit_use_edges_when_actions_disabled() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Selected",
        runner_group_visibility="selected",
        restricted_to_workflows=False,
        accessible_repo_node_ids=["REPO_1"],
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.actions_enabled_repository_node_ids_for_org.return_value = []
    lookup.branch_node_ids_for_org.return_value = [("REPO_1", "BRANCH_1")]
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [ek.IS_ELIGIBLE_FOR]
    lookup.branch_node_ids_for_org.assert_not_called()


def test_inherited_org_runner_group_access_requires_enterprise_workflow_policy_to_be_open() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Selected",
        runner_group_visibility="selected",
        restricted_to_workflows=False,
        inherited=True,
        accessible_repo_node_ids=["REPO_1"],
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group.return_value = (
        True
    )
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [ek.IS_ELIGIBLE_FOR]
    lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group.assert_called_once_with(
        "ORG_1", "Selected"
    )
    lookup.actions_enabled_repository_node_ids_for_org.assert_not_called()
    lookup.branch_node_ids_for_org.assert_not_called()


def test_org_runner_group_access_all_visibility_emits_traversable_create_access_for_members_with_creation_capability() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        allows_public_repositories=True,
        restricted_to_workflows=False,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.repository_node_ids_for_org.return_value = []
    lookup.actions_enabled_repositories_for_org.return_value = "all"
    lookup.members_can_create_repository.return_value = (True, False, False, False)
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
    ]
    assert [edge.start.value for edge in edges] == ["ORG_1_owners", "ORG_1_members"]
    assert {edge.end.value for edge in edges} == {"ORG_1_runner_group_1"}
    assert all(edge.properties.traversable is True for edge in edges)
    query = edges[1].properties.query_composition
    assert "GH_CanCreateRepositories" in query
    assert "GH_CanCreatePublicRepositories" in query
    assert "GH_CanCreateInternalRepositories" in query
    assert "GH_CanCreatePrivateRepositories" in query
    assert "GH_Contains" in query
    assert "org.actions_enabled_repositories = 'all'" in query
    assert "coalesce(group.restricted_to_workflows, true) = false" in query


def test_org_runner_group_access_without_public_access_requires_private_or_internal_creation() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        allows_public_repositories=False,
        restricted_to_workflows=False,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.private_repository_node_ids_for_org.return_value = []
    lookup.actions_enabled_repositories_for_org.return_value = "all"
    lookup.members_can_create_repository.return_value = (True, True, False, False)
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS
    ]
    assert edges[0].start.value == "ORG_1_owners"
    assert edges[0].properties.traversable is True
    query = edges[0].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in query
    assert "GH_CanCreatePrivateRepositories" in query
    assert "GH_CanCreateRepositories" not in query
    assert "GH_CanCreatePublicRepositories" not in query


def test_org_runner_group_access_private_visibility_requires_private_or_internal_creation() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Private",
        runner_group_visibility="private",
        allows_public_repositories=True,
        restricted_to_workflows=False,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.private_repository_node_ids_for_org.return_value = []
    lookup.actions_enabled_repositories_for_org.return_value = "all"
    lookup.members_can_create_repository.return_value = (False, False, True, False)
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS,
    ]
    assert [edge.start.value for edge in edges] == ["ORG_1_owners", "ORG_1_members"]
    assert all(edge.properties.traversable is True for edge in edges)
    query = edges[1].properties.query_composition
    assert "GH_CanCreateInternalRepositories" in query
    assert "GH_CanCreatePrivateRepositories" in query
    assert "GH_CanCreateRepositories" not in query
    assert "GH_CanCreatePublicRepositories" not in query


def test_org_runner_group_access_selected_visibility_does_not_emit_latent_access() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Selected",
        runner_group_visibility="selected",
        allows_public_repositories=True,
        accessible_repo_node_ids=[],
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.members_can_create_repository.return_value = (True, True, True, True)
    access._lookup = lookup

    assert list(access.edges) == []


def test_org_runner_group_access_does_not_emit_create_access_when_new_repositories_do_not_have_actions_enabled() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        allows_public_repositories=True,
        restricted_to_workflows=False,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.repository_node_ids_for_org.return_value = []
    lookup.actions_enabled_repositories_for_org.return_value = "selected"
    lookup.members_can_create_repository.return_value = (True, True, True, True)
    access._lookup = lookup

    assert list(access.edges) == []


def test_inherited_org_runner_group_create_access_requires_enterprise_workflow_policy_to_be_open() -> None:
    access = OrgRunnerGroupAccess(
        runner_group_id=1,
        runner_group_name="Default",
        runner_group_visibility="all",
        allows_public_repositories=True,
        restricted_to_workflows=False,
        inherited=True,
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.repository_node_ids_for_org.return_value = []
    lookup.actions_enabled_repositories_for_org.return_value = "all"
    lookup.members_can_create_repository.return_value = (False, False, False, False)
    lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group.return_value = (
        False
    )
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.CAN_CREATE_REPOSITORY_WITH_RUNNER_ACCESS
    ]
    assert edges[0].properties.traversable is True
    query = edges[0].properties.query_composition
    assert "GH_InheritedFrom" in query
    assert "coalesce(enterprise_group.restricted_to_workflows, true) = false" in query


def test_native_org_runner_group_membership_emits_structural_and_capability_edges() -> None:
    membership = OrgRunnerGroupMembership(
        runner_group_id=1,
        runner_group_name="Default",
        runner_id=9,
        runner_group_visibility="all",
        org_login="acme",
    )
    membership._lookup = SimpleNamespace(org_id_for_login=lambda _login: "ORG_1")

    edges = list(membership.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS, ek.HAS_RUNNER]
    assert edges[0].start.value == "ORG_1_runner_group_1"
    assert edges[0].end.value == "ORG_1_runner_9"
    assert edges[0].properties.traversable is False
    assert edges[1].start.value == "ORG_1_runner_group_1"
    assert edges[1].end.value == "ORG_1_runner_9"
    assert edges[1].properties.traversable is True


def test_enterprise_organization_lookup_filters_to_enterprise() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.enterprise_organizations (id VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('ORG_1', 'ENT_1'), ('ORG_2', 'ENT_1'), ('ORG_3', 'ENT_2')"
    )

    assert GithubLookup(connection).enterprise_organization_node_ids("ENT_1") == [
        ("ORG_1",),
        ("ORG_2",),
    ]


def test_actions_enabled_repositories_lookup_returns_org_policy() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.organizations (login VARCHAR, actions_enabled_repositories VARCHAR)"
    )
    connection.execute("INSERT INTO github.organizations VALUES ('acme', 'all')")

    assert GithubLookup(connection).actions_enabled_repositories_for_org("acme") == "all"


def test_inherited_org_runner_group_lookup_resolves_all_and_selected_assignments() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.enterprise_organizations (id VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_groups (id BIGINT, name VARCHAR, visibility VARCHAR, restricted_to_workflows BOOLEAN, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_organizations (node_id VARCHAR, runner_group_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_memberships (runner_group_id BIGINT, runner_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('ORG_1', 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_groups VALUES (1, 'Default', 'all', false, 'ENT_1'), (2, 'Selected', 'selected', true, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_group_organizations VALUES ('ORG_1', 2, 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_group_memberships VALUES (1, 9, 'ENT_1'), (2, 10, 'ENT_1')"
    )

    lookup = GithubLookup(connection)

    assert (
        lookup.enterprise_runner_group_node_id_for_inherited_org_group(
            "ORG_1", "Default"
        )
        == "ENT_1_runner_group_1"
    )
    assert (
        lookup.enterprise_runner_group_node_id_for_inherited_org_group(
            "ORG_1", "Selected"
        )
        == "ENT_1_runner_group_2"
    )
    assert (
        lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group(
            "ORG_1", "Default"
        )
        is False
    )
    assert (
        lookup.enterprise_runner_group_restricted_to_workflows_for_inherited_org_group(
            "ORG_1", "Selected"
        )
        is True
    )
    assert lookup.enterprise_runner_node_ids_for_inherited_org_group(
        "ORG_1", "Default"
    ) == [("ENT_1_runner_9",)]
    assert lookup.enterprise_runner_node_ids_for_inherited_org_group(
        "ORG_1", "Selected"
    ) == [("ENT_1_runner_10",)]


def test_inherited_org_runner_group_lookup_skips_missing_and_ambiguous_matches() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.enterprise_organizations (id VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_groups (id BIGINT, name VARCHAR, visibility VARCHAR, restricted_to_workflows BOOLEAN, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_organizations (node_id VARCHAR, runner_group_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('ORG_1', 'ENT_1'), ('ORG_1', 'ENT_2')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_groups VALUES (1, 'Default', 'all', false, 'ENT_1'), (2, 'Default', 'all', false, 'ENT_2')"
    )

    lookup = GithubLookup(connection)

    assert (
        lookup.enterprise_runner_group_node_id_for_inherited_org_group(
            "ORG_1", "Missing"
        )
        is None
    )
    assert (
        lookup.enterprise_runner_group_node_id_for_inherited_org_group(
            "ORG_1", "Default"
        )
        is None
    )
