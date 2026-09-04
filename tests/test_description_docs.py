import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "extension" / "schema.json"
NODE_DOCS_DIR = ROOT / "descriptions" / "nodes"
EDGE_DOCS_DIR = ROOT / "descriptions" / "edges"


def _schema_gh_kinds(key: str) -> set[str]:
    schema = json.loads(SCHEMA_PATH.read_text())
    return {entry["name"] for entry in schema[key] if entry["name"].startswith("GH_")}


def _doc_kinds(directory: Path) -> set[str]:
    return {path.stem for path in directory.glob("GH_*.md")}


def test_gh_node_descriptions_cover_schema_and_include_structure():
    schema_kinds = _schema_gh_kinds("node_kinds")
    assert _doc_kinds(NODE_DOCS_DIR) == schema_kinds

    for kind in schema_kinds:
        text = (NODE_DOCS_DIR / f"{kind}.md").read_text()
        assert text.startswith(f"# {kind}\n")
        assert "## Properties\n" in text
        assert "## General Information\n" in text
        assert "## Diagram\n" in text
        assert "```mermaid\n" in text
        assert text.index("## General Information\n") < text.index("## Properties\n")


def test_gh_edge_descriptions_cover_schema_and_include_structure():
    schema_kinds = _schema_gh_kinds("relationship_kinds")
    assert _doc_kinds(EDGE_DOCS_DIR) == schema_kinds

    for kind in schema_kinds:
        text = (EDGE_DOCS_DIR / f"{kind}.md").read_text()
        assert text.startswith(f"# {kind}\n")
        assert "## Edge Schema\n" in text
        assert "## General Information\n" in text
        assert "## Diagram\n" in text
        assert "```mermaid\n" in text
        assert text.index("## General Information\n") < text.index("## Edge Schema\n")
