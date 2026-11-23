"""Compare the collector's SAML graph output with a stored baseline.

Regenerate the baseline from the collector with ``UPDATE_SAML_BASELINE=1``.
"""

import gzip
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from openhound.core.progress import Progress

from openhound_github import source as source_module
from openhound_github.main import convert, preproc

BASELINE_DIR = Path(__file__).parent / "test_data" / "saml_baseline"


def _read_graph(graph_dir: Path) -> dict[str, list[dict]]:
    """Merge the converter's graph files into one order-independent document.

    The converter splits output across files and stamps every node with the
    time it ran, so file layout and ``last_seen`` are normalized away. Nodes and
    edges are sorted; everything else is exactly what the collector wrote.
    """
    graph: dict[str, list[dict]] = {"nodes": [], "edges": []}
    for path in graph_dir.rglob("*.json"):
        content = json.loads(path.read_text()).get("graph", {})
        for kind in graph:
            graph[kind].extend(content.get(kind, []))
    for node in graph["nodes"]:
        node["properties"].pop("last_seen", None)
    graph["nodes"].sort(key=lambda node: node["id"])
    graph["edges"].sort(key=json.dumps)
    return graph


def test_saml_graph_matches_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run native rows through preprocess and convert and compare the graph exactly.

    The converter builds its resource list from the configured source, so the
    test configures GitHub App credentials with no installations: this exposes
    the enterprise and organization resources without contacting GitHub.
    """
    for name, value in {
        "CLIENT_ID": "example-client",
        "KEY_PATH": "/nonexistent/example.pem",
        "ENTERPRISE_NAME": "example-enterprise",
    }.items():
        monkeypatch.setenv(f"SOURCES__GITHUB__CREDENTIALS__{name}", value)
    monkeypatch.setenv("SOURCES__GITHUB__EMIT_LEGACY_SCIM_CORRELATIONS", "false")
    monkeypatch.setattr(
        source_module, "GithubApp", lambda **_: SimpleNamespace(installations=[])
    )
    raw = tmp_path / "raw"
    for table, rows in json.loads((BASELINE_DIR / "input.json").read_text()).items():
        (raw / table).mkdir(parents=True)
        with gzip.open(raw / table / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
            f.writelines(json.dumps(row) + "\n" for row in rows)

    lookup = tmp_path / "lookup.duckdb"
    graph = tmp_path / "graph"
    preproc(raw, lookup, progress=Progress.log)
    convert(raw, graph, progress=Progress.log, lookup_file=lookup)

    actual = _read_graph(graph)
    assert actual["nodes"], "the converter wrote no graph nodes"
    baseline = BASELINE_DIR / "graph.json"
    if os.environ.get("UPDATE_SAML_BASELINE"):
        baseline.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
    assert actual == json.loads(baseline.read_text())
