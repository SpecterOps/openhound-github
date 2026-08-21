import duckdb
import pytest

from openhound_github.lookup import GithubLookup


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
