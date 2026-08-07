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


def test_enterprise_runner_group_with_all_visibility_assigns_every_enterprise_org() -> None:
    group = EnterpriseRunnerGroup(
        id=2,
        name="Enterprise Default",
        visibility="all",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    lookup = MagicMock()
    lookup.enterprise_organization_node_ids.return_value = [("ORG_1",), ("ORG_2",)]
    group._lookup = lookup

    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [
        ek.CONTAINS,
        ek.ASSIGNED_TO,
        ek.ASSIGNED_TO,
    ]
    assert {edge.end.value for edge in edges[1:]} == {"ORG_1", "ORG_2"}
    lookup.enterprise_organization_node_ids.assert_called_once_with("ENT_1")


def test_enterprise_runner_group_with_selected_visibility_does_not_infer_orgs() -> None:
    group = EnterpriseRunnerGroup(
        id=2,
        name="Selected Group",
        visibility="selected",
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )
    lookup = MagicMock()
    group._lookup = lookup

    edges = list(group.edges)

    assert [edge.kind for edge in edges] == [ek.CONTAINS]
    lookup.enterprise_organization_node_ids.assert_not_called()


def test_enterprise_runner_group_membership_contains_enterprise_runner() -> None:
    membership = EnterpriseRunnerGroupMembership(
        runner_group_id=2,
        runner_id=9,
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )

    edge = next(iter(membership.edges))

    assert edge.kind == ek.CONTAINS
    assert edge.start.value == "ENT_1_runner_group_2"
    assert edge.end.value == "ENT_1_runner_9"


def test_enterprise_runner_group_organization_assignment_uses_assigned_to() -> None:
    assignment = EnterpriseRunnerGroupOrganization(
        node_id="ORG_1",
        login="acme-org",
        runner_group_id=2,
        enterprise_node_id="ENT_1",
        enterprise_slug="acme-enterprise",
    )

    edge = next(iter(assignment.edges))

    assert edge.kind == ek.ASSIGNED_TO
    assert edge.start.value == "ENT_1_runner_group_2"
    assert edge.end.value == "ORG_1"


def test_org_runner_group_access_grants_repositories_and_composes_inherited_runners() -> None:
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
    lookup.enterprise_runner_node_ids_for_inherited_org_group.return_value = [
        ("ENT_1_runner_9",)
    ]
    access._lookup = lookup

    edges = list(access.edges)

    assert [edge.kind for edge in edges] == [
        ek.GRANTS_ACCESS_TO,
        ek.CAN_USE_RUNNER,
    ]
    assert edges[0].start.value == "ORG_1_runner_group_1"
    assert edges[0].end.value == "REPO_1"
    assert edges[1].start.value == "REPO_1"
    assert edges[1].end.value == "ENT_1_runner_9"
    assert edges[1].properties.composed is True
    assert "GH_InheritedFrom" in edges[1].properties.query_composition


def test_native_org_runner_group_membership_composes_can_use_runner_through_access() -> None:
    membership = OrgRunnerGroupMembership(
        runner_group_id=1,
        runner_group_name="Default",
        runner_id=9,
        runner_group_visibility="all",
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "ORG_1"
    lookup.repository_node_ids_for_org.return_value = [("REPO_1",)]
    membership._lookup = lookup

    edges = list(membership.edges)

    assert [edge.kind for edge in edges] == [ek.CAN_USE_RUNNER, ek.CONTAINS]
    assert edges[0].properties.composed is True
    assert "GH_GrantsAccessTo" in edges[0].properties.query_composition
    assert edges[1].start.value == "ORG_1_runner_group_1"
    assert edges[1].end.value == "ORG_1_runner_9"


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


def test_inherited_org_runner_group_lookup_resolves_all_and_selected_assignments() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github")
    connection.execute(
        "CREATE TABLE github.enterprise_organizations (id VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_groups (id BIGINT, name VARCHAR, visibility VARCHAR, enterprise_node_id VARCHAR)"
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
        "INSERT INTO github.enterprise_runner_groups VALUES (1, 'Default', 'all', 'ENT_1'), (2, 'Selected', 'selected', 'ENT_1')"
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
        "CREATE TABLE github.enterprise_runner_groups (id BIGINT, name VARCHAR, visibility VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github.enterprise_runner_group_organizations (node_id VARCHAR, runner_group_id BIGINT, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github.enterprise_organizations VALUES ('ORG_1', 'ENT_1'), ('ORG_1', 'ENT_2')"
    )
    connection.execute(
        "INSERT INTO github.enterprise_runner_groups VALUES (1, 'Default', 'all', 'ENT_1'), (2, 'Default', 'all', 'ENT_2')"
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
