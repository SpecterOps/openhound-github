import gzip
import json
from pathlib import Path

import duckdb
from openhound.core.progress import Progress

from openhound_github.main import preproc


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
