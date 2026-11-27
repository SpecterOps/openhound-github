import gzip
import json
from pathlib import Path

import duckdb
from openhound.core.progress import Progress

from openhound_github.main import preproc
from openhound_github.lookup import GithubLookup


def _write_resource_rows(
    input_path: Path, resource_name: str, rows: list[dict[str, object]]
) -> None:
    resource_dir = input_path / resource_name
    resource_dir.mkdir(exist_ok=True)
    with gzip.open(resource_dir / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row))
            f.write("\n")


def test_preproc_rebuilds_lookup_before_optional_table_becomes_populated(
    tmp_path: Path,
) -> None:
    _write_resource_rows(tmp_path, "organizations", [{"id": "ORG_1", "login": "acme"}])
    lookup_file = tmp_path / "lookup.duckdb"

    preproc(tmp_path, lookup_file, progress=Progress.log)

    with duckdb.connect(str(lookup_file)) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM github.team_external_groups"
        ).fetchone() == (0,)

    _write_resource_rows(
        tmp_path,
        "team_external_groups",
        [
            {
                "org_login": "acme",
                "team_database_id": 7,
                "external_group_id": 100,
                "external_group_name": "Engineering",
                "external_group_updated_at": "2026-09-10T00:00:00Z",
            }
        ],
    )

    preproc(tmp_path, lookup_file, progress=Progress.log)

    with duckdb.connect(str(lookup_file)) as connection:
        assert connection.execute(
            "SELECT org_login, team_database_id, external_group_name "
            "FROM github.team_external_groups"
        ).fetchall() == [("acme", 7, "Engineering")]


def test_preproc_loads_installations_and_selected_repository_grants(
    tmp_path: Path,
) -> None:
    _write_resource_rows(
        tmp_path,
        "repositories",
        [
            {"node_id": "REPO_1", "database_id": 101, "org_login": "acme"},
        ],
    )
    _write_resource_rows(
        tmp_path,
        "app_installations",
        [
            {
                "id": 42,
                "app_slug": "release-app",
                "permissions": {"contents": "write"},
                "target_type": "Organization",
                "repository_selection": "selected",
                "environment_slug": "acme",
            },
        ],
    )
    _write_resource_rows(
        tmp_path,
        "app_installation_repo_access",
        [
            {
                "installation_node_id": "GH_AppInstallation_42",
                "repository_database_id": 101,
                "org_login": "acme",
            },
        ],
    )
    lookup_file = tmp_path / "lookup.duckdb"

    preproc(tmp_path, lookup_file, progress=Progress.log)

    with duckdb.connect(str(lookup_file)) as connection:
        lookup = GithubLookup(connection)
        assert (
            lookup.app_installation_node_id_for_repository("release-app", "REPO_1")
            == "GH_AppInstallation_42"
        )
        assert connection.execute(
            "SELECT json_extract_string(permissions, '$.contents') "
            "FROM github.app_installations WHERE id = 42"
        ).fetchone() == ("write",)


def test_preproc_loads_branch_creation_scope_and_repository_membership(tmp_path):
    _write_resource_rows(
        tmp_path,
        "repositories",
        [
            {
                "node_id": "R_1",
                "org_login": "acme",
                "default_branch": "main",
            }
        ],
    )
    _write_resource_rows(
        tmp_path,
        "branches",
        [
            {
                "id": "B_1",
                "repository_node_id": "R_1",
                "name": "main",
            }
        ],
    )
    _write_resource_rows(
        tmp_path,
        "scopes",
        [
            {
                "org_login": "acme",
                "org_node_id": "O_1",
                "scope_type": "repository_branch_creation",
                "scope": "unrestricted",
            }
        ],
    )
    lookup_file = tmp_path / "lookup.duckdb"

    preproc(tmp_path, lookup_file, progress=Progress.log)

    with duckdb.connect(str(lookup_file)) as con:
        lookup = GithubLookup(con)
        assert lookup.branch_creation_scope_available("acme", "O_1")
        assert lookup.branch_creation_repositories_for_org("acme") == [("R_1",)]
        assert (
            lookup.canonical_scope_target_count(
                "acme", "repository_branch_creation", "unrestricted"
            )
            == 1
        )
