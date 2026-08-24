import duckdb
import pytest

from openhound_github.lookup import GithubLookup
from openhound_github.transforms import ensure_optional_input_tables


def test_github_lookup_accepts_plain_schema_identifiers() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github_test")
    connection.execute(
        "CREATE TABLE github_test.projected_enterprise_teams "
        "(node_id VARCHAR, org_login VARCHAR, slug VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github_test.projected_enterprise_teams VALUES (?, ?, ?)",
        ["TEAM_1", "acme", "ent:security"],
    )

    lookup = GithubLookup(connection, schema="github_test")

    assert lookup.projected_enterprise_team_id("acme", "ent:security") == "TEAM_1"


def test_github_lookup_rejects_untrusted_schema_identifiers() -> None:
    connection = duckdb.connect(":memory:")

    with pytest.raises(ValueError, match="Invalid DuckDB schema identifier"):
        GithubLookup(connection, schema="github; DROP SCHEMA github")


def test_external_group_for_team_is_scoped_to_org_login() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github_test")
    connection.execute(
        "CREATE TABLE github_test.team_external_groups "
        "(org_login VARCHAR, team_database_id BIGINT, "
        "external_group_id BIGINT, external_group_name VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github_test.team_external_groups VALUES "
        "('acme', 7, 100, 'Acme Engineering'), "
        "('other', 7, 200, 'Other Engineering')"
    )

    lookup = GithubLookup(connection, schema="github_test")

    assert lookup.external_group_for_team("acme", 7) == (100, "Acme Engineering")
    assert lookup.external_group_for_team("other", 7) == (200, "Other Engineering")


def test_scim_group_id_for_team_external_group_is_scoped_to_enterprise_org() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github_test")
    connection.execute(
        "CREATE TABLE github_test.enterprise_organizations "
        "(login VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github_test.enterprise_scim_groups "
        "(id VARCHAR, display_name VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github_test.enterprise_organizations VALUES "
        "('acme', 'ENT_1'), ('other', 'ENT_2')"
    )
    connection.execute(
        "INSERT INTO github_test.enterprise_scim_groups VALUES "
        "('SCIM_1', 'Engineering', 'ENT_1'), "
        "('SCIM_2', 'Engineering', 'ENT_2')"
    )

    lookup = GithubLookup(connection, schema="github_test")

    assert (
        lookup.scim_group_id_for_team_external_group("acme", "Engineering")
        == "SCIM_1"
    )
    assert (
        lookup.scim_group_id_for_team_external_group("other", "Engineering")
        == "SCIM_2"
    )


def test_scim_group_id_for_team_external_group_skips_ambiguous_names() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github_test")
    connection.execute(
        "CREATE TABLE github_test.enterprise_organizations "
        "(login VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE github_test.enterprise_scim_groups "
        "(id VARCHAR, display_name VARCHAR, enterprise_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO github_test.enterprise_organizations VALUES ('acme', 'ENT_1')"
    )
    connection.execute(
        "INSERT INTO github_test.enterprise_scim_groups VALUES "
        "('SCIM_1', 'Engineering', 'ENT_1'), "
        "('SCIM_2', 'Engineering', 'ENT_1')"
    )

    lookup = GithubLookup(connection, schema="github_test")

    assert lookup.scim_group_id_for_team_external_group("acme", "Engineering") is None


def test_scim_group_id_for_team_external_group_skips_org_only_context() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA github_test")
    ensure_optional_input_tables(connection, schema="github_test")

    lookup = GithubLookup(connection, schema="github_test")

    assert lookup.scim_group_id_for_team_external_group("acme", "Engineering") is None
