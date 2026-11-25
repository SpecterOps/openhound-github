import duckdb
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.transforms import ensure_app_installation_input_tables


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        ensure_app_installation_input_tables(con, "inventory")
        con.execute(
            "INSERT INTO inventory.repositories (node_id, database_id, org_login) VALUES "
            "('REPO_1', 101, 'acme'), ('REPO_2', 102, 'acme'), "
            "('OTHER_REPO', 103, 'other-org')"
        )
        yield con


def _install(
    con,
    installation_id,
    org="acme",
    selection="all",
    target="Organization",
    suspended=None,
):
    con.execute(
        "INSERT INTO inventory.app_installations "
        "(id, app_slug, environment_slug, repository_selection, target_type, suspended_at) "
        "VALUES (?, 'release-app', ?, ?, ?, ?)",
        [installation_id, org, selection, target, suspended],
    )


def test_all_repository_resolution_stays_within_the_owning_organization(connection):
    _install(connection, 1)
    _install(connection, 2, org="other-org")
    lookup = GithubLookup(connection, schema="inventory")

    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1")
        == "GH_AppInstallation_1"
    )
    assert (
        lookup.app_installation_node_id_for_repository("RELEASE-APP", "REPO_2")
        == "GH_AppInstallation_1"
    )
    assert (
        lookup.app_installation_node_id_for_repository("release-app", "OTHER_REPO")
        == "GH_AppInstallation_2"
    )


@pytest.mark.parametrize(
    ("grant_id", "grant_repository", "grant_org", "expected"),
    [
        ("GH_AppInstallation_1", 101, "ACME", "GH_AppInstallation_1"),
        ("GH_AppInstallation_1", 102, "acme", None),
        ("GH_AppInstallation_1", 101, "other-org", None),
        ("GH_AppInstallation_2", 101, "acme", None),
    ],
)
def test_selected_access_requires_matching_installation_repository_and_org(
    connection, grant_id, grant_repository, grant_org, expected
):
    _install(connection, 1, selection="selected")
    connection.execute(
        "INSERT INTO inventory.app_installation_repo_access VALUES (?, ?, ?)",
        [grant_id, grant_repository, grant_org],
    )
    lookup = GithubLookup(connection, schema="inventory")

    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1")
        == expected
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"selection": "selected"},
        {"selection": None},
        {"target": "Enterprise"},
        {"suspended": "2026-11-20T00:00:00Z"},
        {"org": "other-org"},
    ],
)
def test_installations_without_known_active_access_are_not_resolved(
    connection, settings
):
    _install(connection, 1, **settings)
    lookup = GithubLookup(connection, schema="inventory")

    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1") is None
    )


def test_duplicate_records_are_deduplicated_but_ambiguous_installations_are_unresolved(
    connection,
):
    _install(connection, 1)
    _install(connection, 1)
    lookup = GithubLookup(connection, schema="inventory")
    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1")
        == "GH_AppInstallation_1"
    )

    _install(connection, 2)
    lookup = GithubLookup(connection, schema="inventory")
    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1") is None
    )


def test_legacy_installation_context_and_missing_matches(connection):
    _install(connection, 1, org=None)
    connection.execute("UPDATE inventory.app_installations SET org_login = 'ACME'")
    lookup = GithubLookup(connection, schema="inventory")

    assert (
        lookup.app_installation_node_id_for_repository("release-app", "REPO_1")
        == "GH_AppInstallation_1"
    )
    assert (
        lookup.app_installation_node_id_for_repository("missing-app", "REPO_1") is None
    )
    assert (
        lookup.app_installation_node_id_for_repository("release-app", "MISSING_REPO")
        is None
    )


def test_empty_inventory_returns_no_match():
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE SCHEMA inventory")
        ensure_app_installation_input_tables(con, "inventory")

        assert (
            GithubLookup(
                con, schema="inventory"
            ).app_installation_node_id_for_repository("release-app", "REPO_1")
            is None
        )
