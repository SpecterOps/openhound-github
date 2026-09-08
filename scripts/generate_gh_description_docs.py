#!/usr/bin/env python3
"""Generate GH_ node and edge description docs from collector metadata.

The collector model is the source of truth for property fields and registered
relationship endpoints. Existing explanatory prose is preserved when a doc
already exists; missing docs fall back to the schema description.
"""

from __future__ import annotations

import inspect
import json
import re
import types
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import openhound_github.models  # noqa: F401 - importing registers assets

from openhound_github.graph import GHNodeProperties
from openhound_github.main import app


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "extension" / "schema.json"
NODE_DOCS_DIR = ROOT / "descriptions" / "nodes"
EDGE_DOCS_DIR = ROOT / "descriptions" / "edges"

COMMON_PROPERTY_DESCRIPTIONS = {
    "name": "The node name used for matching and display.",
    "displayname": "The human-readable display name.",
    "environmentid": "The identifier of the GitHub environment where this node was collected.",
    "last_seen": "The timestamp when this node was last observed during collection.",
    "node_id": "The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available.",
}

SCHEMA_ONLY_EDGE_ENDPOINTS = {
    "GH_CanAssumeIdentity": [("GH_Repository", "External cloud identity", True)],
    "GH_CreateRepository": [("GH_OrgRole", "GH_Organization", False)],
    "GH_ManageOrganizationWebhooks": [("GH_OrgRole", "GH_Organization", False)],
    "GH_OrgBypassCodeScanningDismissalRequests": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_OrgBypassSecretScanningClosureRequests": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_OrgReviewAndManageSecretScanningBypassRequests": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_OrgReviewAndManageSecretScanningClosureRequests": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_ReadOrganizationActionsUsageMetrics": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_ReadOrganizationCustomOrgRole": [("GH_OrgRole", "GH_Organization", False)],
    "GH_ReadOrganizationCustomRepoRole": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_SyncedTo": [("External identity", "GH_User", True)],
    "GH_WriteOrganizationActionsSecrets": [("GH_OrgRole", "GH_Organization", False)],
    "GH_WriteOrganizationActionsSettings": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_WriteOrganizationActionsVariables": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_WriteOrganizationCustomOrgRole": [
        ("GH_OrgRole", "GH_Organization", True)
    ],
    "GH_WriteOrganizationCustomRepoRole": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
    "GH_WriteOrganizationNetworkConfigurations": [
        ("GH_OrgRole", "GH_Organization", False)
    ],
}


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text if text.endswith((".", "!", "?")) else f"{text}."


def humanize(name: str) -> str:
    return name.replace("_", " ")


def format_type(annotation: Any) -> str:
    if annotation is None or annotation is type(None):
        return "null"
    if isinstance(annotation, str):
        return {
            "str": "string",
            "int": "integer",
            "bool": "boolean",
            "float": "number",
        }.get(annotation, annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1:
            return format_type(non_none[0])
        return " or ".join(format_type(arg) for arg in non_none)
    if origin is list:
        return f"list[{format_type(args[0])}]" if args else "list"
    if origin is dict:
        return "object"

    names = {
        str: "string",
        int: "integer",
        bool: "boolean",
        float: "number",
    }
    if annotation in names:
        return names[annotation]
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def doc_attribute_descriptions(cls: type) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    doc = inspect.getdoc(cls) or ""
    in_attributes = False
    current_name: str | None = None
    for line in doc.splitlines():
        if line.strip() == "Attributes:":
            in_attributes = True
            continue
        if not in_attributes:
            continue
        match = re.match(r"\s{4,}([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
        if match:
            current_name = match.group(1)
            descriptions[current_name] = match.group(2).strip()
            continue
        if current_name and line.strip():
            descriptions[current_name] = f"{descriptions[current_name]} {line.strip()}"
        elif not line.strip():
            current_name = None
    return descriptions


def property_rows(properties_cls: type | None) -> list[tuple[str, str, str]]:
    properties_cls = properties_cls or GHNodeProperties
    annotations: dict[str, Any] = {}
    descriptions = dict(COMMON_PROPERTY_DESCRIPTIONS)
    for cls in reversed(properties_cls.__mro__):
        if cls in (object,):
            continue
        annotations.update(getattr(cls, "__annotations__", {}))
        descriptions.update(doc_attribute_descriptions(cls))

    rows = []
    for name, annotation in annotations.items():
        description = descriptions.get(name, sentence(f"The {humanize(name)} value"))
        rows.append((name, format_type(annotation), sentence(description)))
    return rows


def extract_general_information(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text().strip()
    match = re.search(r"^## (?:General Information|Description)\s*$", text, re.MULTILINE)
    if match:
        text = text[match.end() :].strip()
    else:
        text = re.sub(r"^# .+?\n+", "", text, count=1).strip()
    text = re.split(r"^## Diagram\s*$", text, maxsplit=1, flags=re.MULTILINE)[0].strip()
    text = re.sub(r"\n```mermaid\n.*?\n```\s*$", "", text, flags=re.DOTALL).strip()
    return text or None


def mermaid_id(label: str, index: int) -> str:
    return f"n{index}"


def mermaid_diagram(
    relationships: list[tuple[str, str, str, bool]],
    focal_node: str | None = None,
) -> str:
    if not relationships and focal_node:
        return f'graph LR\n    n0["{focal_node}"]'

    labels: list[str] = []
    for start, end, _, _ in relationships:
        if start not in labels:
            labels.append(start)
        if end not in labels:
            labels.append(end)
    if focal_node and focal_node not in labels:
        labels.insert(0, focal_node)

    lines = ["graph LR"]
    for index, label in enumerate(labels):
        lines.append(f'    {mermaid_id(label, index)}["{label}"]')
    for start, end, edge_kind, traversable in relationships:
        start_id = mermaid_id(start, labels.index(start))
        end_id = mermaid_id(end, labels.index(end))
        arrow = "-->" if traversable else "-.->"
        lines.append(f"    {start_id} {arrow}|{edge_kind}| {end_id}")
    return "\n".join(lines)


def node_relationships(node_kind: str, edge_defs: list[Any]) -> list[tuple[str, str, str, bool]]:
    rows = {
        (edge.start, edge.end, edge.kind, edge.traversable)
        for edge in edge_defs
        if edge.kind.startswith("GH_")
        and edge.start.startswith("GH_")
        and edge.end.startswith("GH_")
        and node_kind in (edge.start, edge.end)
    }
    return sorted(rows)


def edge_relationships(edge_kind: str, edge_defs: list[Any]) -> list[tuple[str, str, bool]]:
    rows = {
        (edge.start, edge.end, edge.traversable)
        for edge in edge_defs
        if edge.kind == edge_kind
    }
    if not rows:
        rows = set(SCHEMA_ONLY_EDGE_ENDPOINTS.get(edge_kind, []))
    return sorted(rows)


def render_node_doc(
    kind: str,
    description: str,
    properties_cls: type | None,
    relationships: list[tuple[str, str, str, bool]],
    existing_info: str | None,
) -> str:
    property_table = [
        "| Property | Type | Description |",
        "| --- | --- | --- |",
    ]
    property_table.extend(
        f"| `{name}` | `{type_name}` | {desc} |"
        for name, type_name, desc in property_rows(properties_cls)
    )
    property_table_text = "\n".join(property_table)
    diagram = mermaid_diagram(relationships, focal_node=kind)
    info = existing_info or sentence(description)
    return (
        f"# {kind}\n\n"
        f"## General Information\n\n"
        f"{info}\n\n"
        f"## Properties\n\n"
        f"{property_table_text}\n\n"
        f"## Diagram\n\n"
        f"```mermaid\n{diagram}\n```\n"
    )


def render_edge_doc(
    kind: str,
    description: str,
    relationships: list[tuple[str, str, bool]],
    existing_info: str | None,
) -> str:
    schema_table = [
        "| Source | Destination | Traversable |",
        "| --- | --- | --- |",
    ]
    schema_table.extend(
        f"| `{start}` | `{end}` | `{'true' if traversable else 'false'}` |"
        for start, end, traversable in relationships
    )
    if len(schema_table) == 2:
        schema_table.append("| `Unknown` | `Unknown` | `false` |")
    schema_table_text = "\n".join(schema_table)
    diagram = mermaid_diagram(
        [(start, end, kind, traversable) for start, end, traversable in relationships]
    )
    info = existing_info or sentence(description)
    return (
        f"# {kind}\n\n"
        f"## General Information\n\n"
        f"{info}\n\n"
        f"## Edge Schema\n\n"
        f"{schema_table_text}\n\n"
        f"## Diagram\n\n"
        f"```mermaid\n{diagram}\n```\n"
    )


def main() -> None:
    schema = load_schema()
    node_defs = {node.kind: node for node in app.nodes if node.kind.startswith("GH_")}
    edge_defs = [edge for edge in app.edges if edge.kind.startswith("GH_")]

    node_kinds = {
        node["name"]: node
        for node in schema["node_kinds"]
        if node["name"].startswith("GH_")
    }
    edge_kinds = {
        edge["name"]: edge
        for edge in schema["relationship_kinds"]
        if edge["name"].startswith("GH_")
    }

    NODE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    EDGE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for kind, schema_node in sorted(node_kinds.items()):
        path = NODE_DOCS_DIR / f"{kind}.md"
        node_def = node_defs.get(kind)
        path.write_text(
            render_node_doc(
                kind=kind,
                description=schema_node["description"],
                properties_cls=node_def.properties if node_def else None,
                relationships=node_relationships(kind, edge_defs),
                existing_info=extract_general_information(path),
            )
        )

    for kind, schema_edge in sorted(edge_kinds.items()):
        path = EDGE_DOCS_DIR / f"{kind}.md"
        path.write_text(
            render_edge_doc(
                kind=kind,
                description=schema_edge["description"],
                relationships=edge_relationships(kind, edge_defs),
                existing_info=extract_general_information(path),
            )
        )

    current_node_docs = {path.stem for path in NODE_DOCS_DIR.glob("GH_*.md")}
    current_edge_docs = {path.stem for path in EDGE_DOCS_DIR.glob("GH_*.md")}
    for stale_kind in sorted(current_node_docs - set(node_kinds)):
        (NODE_DOCS_DIR / f"{stale_kind}.md").unlink()
    for stale_kind in sorted(current_edge_docs - set(edge_kinds)):
        (EDGE_DOCS_DIR / f"{stale_kind}.md").unlink()


if __name__ == "__main__":
    main()
