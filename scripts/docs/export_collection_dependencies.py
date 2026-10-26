#!/usr/bin/env python3
"""Render collection dependency tables and SVG diagrams without connecting to MongoDB."""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import tomllib
from dataclasses import asdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CATALOG = ROOT / "scripts/docs/collection_dependencies.json"
DESTINATION = ROOT / "docs/reference/collection-dependencies"
ASSETS = ROOT / "docs/assets/diagrams/collection-dependencies"


def inventory() -> dict[str, dict]:
    """Read database-qualified physical bindings and operational collection ownership.

    Returns:
        Namespaces mapped to their binding names and optional Pydantic schema.
        The same physical name in different databases remains a distinct entry.
    """
    from api.config.operational_collections import OPERATIONAL_COLLECTIONS
    from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS

    mapping = tomllib.loads((ROOT / "api/config/collections.toml").read_text())
    result = {}
    for database, bindings in mapping.items():
        for binding, collection in bindings.items():
            result[f"{database}.{collection}"] = {"binding": binding}
    for field, name in asdict(OPERATIONAL_COLLECTIONS).items():
        if field == "app_controls_document_id":
            continue
        database = (
            "identity"
            if field
            in {"api_sessions", "audit_events", "operational_audit_events", "audit_chain_heads"}
            else "primary"
        )
        result.setdefault(f"{database}.{name}", {"binding": f"OPERATIONAL_COLLECTIONS.{field}"})
    result["identity.audit_outbox"] = {"binding": "audit_outbox in the owning business database"}
    for namespace, row in result.items():
        name = namespace.split(".", 1)[1]
        adapter = COLLECTION_MODEL_ADAPTERS.get(name) if namespace != "bam.samples" else None
        row["schema"] = adapter.json_schema() if adapter else {}
    return result


def slug(namespace: str) -> str:
    """Return a stable documentation/asset anchor for a database-qualified collection."""
    return namespace.replace(".", "-").replace("_", "-")


def group_for(namespace: str, groups: dict) -> str:
    """Assign a physical collection to its documented domain, retaining database ownership."""
    database, name = namespace.split(".", 1)
    if database in {"identity", "knowledgebase"}:
        return database
    for key, group in groups.items():
        if name in group["collections"] and database == "primary":
            return key
    return "operations"


def reference(namespace: str, groups: dict) -> str:
    """Link a namespace to its collection-specific section in the generated reference."""
    return f"[{namespace}]({group_for(namespace, groups)}.md#{slug(namespace)})"


def relationships(catalog: dict, collections: dict) -> list[dict]:
    """Validate reviewed relationships and add explicitly classified provenance links.

    Args:
        catalog: Reviewed field mappings, semantics and source evidence.
        collections: Current physical collection inventory.

    Returns:
        Reviewed links plus shared authorship and optional release-manifest relationships.

    Raises:
        ValueError: A namespace or evidence path no longer exists.
    """
    edges = list(catalog["edges"])
    for namespace, row in collections.items():
        properties = row["schema"].get("properties", {})
        actors = [
            key
            for key in (
                "created_by",
                "updated_by",
                "author",
                "hidden_by",
                "published_by",
                "retired_by",
                "approved_by",
                "content_editors",
                "actor",
            )
            if key in properties
        ]
        if actors:
            edges.append(
                {
                    "source": namespace,
                    "field": " + ".join(actors),
                    "target": "identity.users",
                    "target_field": "username",
                    "kind": "historical actor",
                    "cardinality": "many → historical identity",
                    "notes": "Only populated actor fields apply. Preserve system and historical "
                    "usernames even if no current account exists; never substitute the migration user.",
                    "evidence": "src/coyote3/contracts/schemas/registry.py",
                }
            )
        if namespace.startswith("knowledgebase.") and namespace != "knowledgebase.versions":
            edges.append(
                {
                    "source": "knowledgebase.versions",
                    "field": "collections[].name",
                    "target": namespace,
                    "target_field": "collection namespace (not a row key)",
                    "kind": "optional release manifest",
                    "cardinality": "one release → many products",
                    "notes": "Applies only when this collection is named in a release manifest. "
                    "The manifest does not establish a foreign key from each provider row to versions._id. "
                    "Keep source, release, build and import counts/checksums together.",
                    "evidence": "api/infra/knowledgebase/versions.py",
                }
            )
    for edge in edges:
        for side in ("source", "target"):
            if edge[side] not in collections:
                raise ValueError(f"Unknown namespace: {edge[side]}")
        if not (ROOT / edge["evidence"]).is_file():
            raise ValueError(f"Missing evidence: {edge['evidence']}")
        # Check the leading source field against typed contracts. Dynamic operational
        # records and repository-defined fields are explicitly documented exceptions.
        props = collections[edge["source"]]["schema"].get("properties", {})
        field = re.split(r"[.\[ +(/]", edge["field"])[0]
        if (
            props
            and field not in props
            and field != "_id"
            and not field.startswith("{")
            and not edge.get("repository_field")
        ):
            raise ValueError(f"Unknown source field: {edge['source']}.{field}")
    return edges


def diagram(namespace: str, edges: list[dict]) -> str:
    """Render readable field-to-field arrows with accessible labels using SVG only.

    Args:
        namespace: Collection whose incoming/outgoing references are shown.
        edges: Adjacent reviewed links. Generic historical actors stay in the tables.

    Returns:
        Standalone SVG with wrapped text, scalable dimensions and no external assets.
    """
    rows = [edge for edge in edges if edge["kind"] != "historical actor"]
    y = 92
    shapes = []
    for edge in rows:
        left = [edge["source"], *textwrap.wrap(edge["field"], 56)]
        right = [edge["target"], *textwrap.wrap(edge["target_field"], 56)]
        height = 30 + max(len(left), len(right)) * 19
        for x, lines, target in ((20, left, edge["source"]), (660, right, edge["target"])):
            shapes.append(
                f'<rect x="{x}" y="{y}" width="520" height="{height}" rx="8" '
                f'fill="{"#eee8f5" if target == namespace else "#f4f7fa"}" '
                'stroke="#8c7aa2"/>'
            )
            for i, line in enumerate(lines):
                shapes.append(
                    f'<text x="{x + 14}" y="{y + 24 + i * 19}" '
                    f'font-weight="{"600" if i == 0 else "400"}">{escape(line)}</text>'
                )
        mid = y + height / 2
        shapes.append(
            f'<path d="M540 {mid} H650" stroke="#644781" stroke-width="2" '
            'marker-end="url(#arrow)"/>'
        )
        shapes.append(
            f'<text x="20" y="{y + height + 19}" class="kind">'
            f"{escape(edge['kind'])} · {escape(edge['cardinality'])}</text>"
        )
        y += height + 45
    if not rows:
        shapes.append(
            '<text x="20" y="115">No typed business-document reference is declared; '
            "see provenance and provider lookup notes in the table.</text>"
        )
        y = 155
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{y}" '
        f'viewBox="0 0 1200 {y}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{escape(namespace)} field dependencies</title>\n'
        '<desc id="description">Each arrow goes from the stored source field to its '
        "referenced key or lookup target. Arrows are not MongoDB foreign-key constraints.</desc>\n"
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" '
        'fill="#644781"/></marker></defs>\n'
        "<style>text{font:15px sans-serif;fill:#263449}.kind{font-size:13px;fill:#655774}</style>\n"
        f'<rect width="1200" height="{y}" fill="white"/>\n'
        f'<text x="20" y="32" style="font-size:23px;font-weight:600">{escape(namespace)}</text>\n'
        '<text x="20" y="61">Source field → target key · See the relationship table for conditions and migration rules.</text>\n'
        + "\n".join(shapes)
        + "\n</svg>\n"
    )


def render(catalog: dict, collections: dict, edges: list[dict]) -> dict[Path, str]:
    """Build domain pages, reverse-reference tables and diagrams without writing files.

    Args:
        catalog: Reviewed domain grouping and collection notes.
        collections: Database-qualified physical bindings with optional schemas.
        edges: Validated field relationships, including shared provenance links.

    Returns:
        Destination paths mapped to complete Markdown or standalone SVG content.
    """
    from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS

    output = {}
    groups = catalog["groups"]
    index = [
        "# Collection inventory",
        "",
        "<!-- GENERATED: scripts/docs/export_collection_dependencies.py -->",
        "",
        "[How to read these relationships and plan a migration](README.md)",
        "",
        "Every physical binding in `api/config/collections.toml` and every operational collection",
        "is listed below. Database labels are logical services, not deployment database names.",
        "",
        "| Namespace | Dependency reference | Binding |",
        "| --- | --- | --- |",
    ]
    for namespace, row in sorted(collections.items()):
        index.append(f"| `{namespace}` | {reference(namespace, groups)} | `{row['binding']}` |")
    unbound = sorted(set(COLLECTION_MODEL_ADAPTERS) - {n.split(".", 1)[1] for n in collections})
    index += [
        "",
        "## Contracts without a current physical binding",
        "",
        "These registered schemas do not establish an active database collection binding:",
        "",
        *[
            f"- `{name}`: inspect its importer/consumer before scheduling migration; do not infer a database from the model name."
            for name in unbound
        ],
        "",
    ]
    output[DESTINATION / "inventory.md"] = "\n".join(index)
    for group, definition in groups.items():
        sources = sorted(
            {
                e["evidence"]
                for e in edges
                if group_for(e["source"], groups) == group
                or group_for(e["target"], groups) == group
            }
        )
        lines = [
            f"# {definition['title']}",
            "",
            "<!-- GENERATED: scripts/docs/export_collection_dependencies.py -->",
            "",
            "[Relationship guide](README.md) · [All collections](inventory.md)",
            "",
            "Arrows run from the referencing field to the target. Snapshot and historical-actor",
            "links preserve provenance; they do not require a live target on every read.",
            "",
        ]
        for namespace, row in sorted(collections.items()):
            if group_for(namespace, groups) != group:
                continue
            adjacent = [e for e in edges if namespace in (e["source"], e["target"])]
            name = namespace.split(".", 1)[1]
            lines += [
                f"## {namespace}",
                "",
                f'<a id="{slug(namespace)}"></a>',
                "",
                f"Binding: `{row['binding']}`.",
                "",
            ]
            description = row["schema"].get("description", "")
            if description:
                lines += [description.split("\n")[0], ""]
            if note := catalog["notes"].get(namespace):
                lines += [note, ""]
            if namespace.startswith("knowledgebase.cosmic_") and "record_key" in row["schema"].get(
                "properties", {}
            ):
                lines += [
                    "Provider product rows retain `record_key` and `source_row`. The latter is an opaque",
                    "provider payload: its columns are release-specific, not declared Coyote3 foreign keys.",
                    "Do not infer a gene/transcript/variant join from a similarly named vendor column.",
                    "",
                ]
            if row["schema"]:
                fields = ", ".join(f"`{field}`" for field in row["schema"].get("properties", {}))
                lines += [
                    f"Declared top-level fields: {fields}.",
                    "",
                    f"[Field types and validation](../mongodb-collections.md#{name}). `_id` may also be retained by an open collection model.",
                    "",
                ]
            else:
                lines += [
                    "Repository-defined storage; no collection-model adapter is registered for this physical namespace.",
                    "",
                ]
            asset = f"{slug(namespace)}.svg"
            output[ASSETS / asset] = diagram(namespace, adjacent)
            lines += [
                f"![{namespace} field relationships](../../assets/diagrams/collection-dependencies/{asset})",
                "",
                f"[Open full-size diagram](../../assets/diagrams/collection-dependencies/{asset})",
                "",
                "### Outgoing dependencies",
                "",
            ]
            for direction in ("out", "in"):
                if direction == "in":
                    lines += ["### Incoming references and migration impact", ""]
                selected = [
                    e
                    for e in adjacent
                    if e["source" if direction == "out" else "target"] == namespace
                ]
                if not selected:
                    lines += [
                        "No cross-collection business reference is declared in this catalog for this direction.",
                        "",
                    ]
                    continue
                lines += [
                    "| Source field | Target key | Relationship / multiplicity | Migration and resolution semantics | Evidence |",
                    "| --- | --- | --- | --- | --- |",
                ]
                for e in selected:
                    evidence = sources.index(e["evidence"]) + 1
                    lines.append(
                        f"| {reference(e['source'], groups)}: `{e['field']}` | "
                        f"{reference(e['target'], groups)}: `{e['target_field']}` | "
                        f"{e['kind']}; {e['cardinality']} | {e['notes']} | [S{evidence}](#s{evidence}) |"
                    )
                lines.append("")
        lines += ["## Source evidence", ""]
        for i, source in enumerate(sources, 1):
            lines += [f"### S{i}", "", f"`{source}`", ""]
        output[DESTINATION / f"{group}.md"] = "\n".join(lines)
    return output


def main() -> int:
    """Write diagrams/reference pages, or fail --check when committed output is stale.

    Returns:
        Zero when generated files match or have been written; one for stale output.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    collections = inventory()
    edges = relationships(catalog, collections)
    outputs = render(catalog, collections, edges)
    stale = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if stale:
        print("Stale dependency documentation:\n" + "\n".join(stale))
        return 1
    print(f"[ok] {len(collections)} collections, {len(edges)} relationships, {len(outputs)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
