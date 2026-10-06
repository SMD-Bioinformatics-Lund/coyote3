#!/usr/bin/env python3
"""Download release-specific Ensembl reference definitions and install VEP metadata.

Source code is read as data, never executed. Downloads and a provenance manifest
are retained in the output directory. Database writes require --apply and a backup.
"""

from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import tinyhtml5
from bson import BSON, json_util
from dotenv import dotenv_values
from PIL import Image
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.reference import VepMetadataDoc  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from scripts.knowledgebase.vep_diagram_storage import (  # noqa: E402
    seed_diagram,
    split_diagram,
    store_diagram,
)

SEED = ROOT / "api/config/bootstrap/reference/vep_metadata.seed.ndjson.gz"
POLICY = Path(__file__).with_name("vep_metadata_policy.json")
CONSEQUENCES = "modules/EnsEMBL/Web/Document/HTML/ConsequenceTable.pm"
CLASSIFICATION = "ensembl/htdocs/info/genome/variation/prediction/classification.html"
CACHE = "docs/htdocs/info/docs/tools/vep/script/vep_cache.html"
SCALAR = re.compile(r"'(term|desc|acc|impact)'\s*=>\s*('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")")


def reference_links(release: int) -> dict[str, str]:
    """Return human-readable documentation links for one verified Ensembl archive.

    Args:
        release: Major release; dates are maintained from Ensembl's archive listing.

    Returns:
        Cache, classification and consequence documentation URLs.

    Raises:
        ValueError: No reviewed archive date exists for the requested release.
    """
    archives = json.loads(Path(__file__).with_name("ensembl_archives.json").read_text())
    if str(release) not in archives:
        raise ValueError(f"Unreviewed Ensembl archive for release {release}")
    root = f"https://{archives[str(release)]}.archive.ensembl.org/info/"
    return {
        "source": root + "docs/tools/vep/script/vep_cache.html",
        "vc_translation_source": root + "genome/variation/prediction/classification.html",
        "conseq_translation_source": root + "genome/variation/prediction/predicted_data.html",
    }


def html_rows(text: str) -> list[list[str]]:
    """Return normalized cell text from HTML table rows.

    Args:
        text: Downloaded UTF-8 Ensembl HTML, including unexpanded template markers.

    Returns:
        Rows of cells in document order with presentation whitespace collapsed.
    """
    root = tinyhtml5.parse(text, namespace_html_elements=False)
    return [
        [" ".join(" ".join(cell.itertext()).split()) for cell in row if cell.tag in ("td", "th")]
        for row in root.iter("tr")
    ]


def consequences(text: str, policy: dict) -> tuple[dict, dict]:
    """Read the literal table used to render Ensembl's predicted_data page.

    Args:
        text: Release-specific ConsequenceTable.pm contents; never evaluated as Perl.
        policy: Reviewed Coyote3 group membership and display-label definitions.

    Returns:
        Consequence translations and their exhaustive, nonoverlapping group map.

    Raises:
        ValueError: Source structure changes, required fields are absent, or a term
            has no reviewed group/label. Unknown terms are not silently classified.
    """
    section = re.search(r"my \$data\s*=\s*\[(.*?)\];", text, re.DOTALL)
    blocks = re.findall(r"\{([^{}]*)\}", section[1]) if section else []
    if not section or len(blocks) < 30 or len(blocks) != section[1].count("'term'"):
        raise ValueError("Unrecognized or incomplete Ensembl consequence source")
    memberships: dict[str, str] = {}
    for group, terms in policy["consequence_groups"].items():
        for term in terms:
            if term in memberships:
                raise ValueError(f"Duplicate group membership: {term}")
            memberships[term] = group
    translations = {}
    for block in blocks:
        fields = {k: ast.literal_eval(v) for k, v in SCALAR.findall(block)}
        if set(fields) != {"term", "desc", "acc", "impact"}:
            raise ValueError("Incomplete consequence table row")
        term = fields["term"]
        if (
            term in translations
            or term not in memberships
            or term not in policy["consequence_labels"]
        ):
            raise ValueError(f"Unreviewed or duplicate consequence: {term}")
        if not re.fullmatch(r"\d{7}", fields["acc"]) or fields["impact"] not in {
            "HIGH",
            "MODERATE",
            "LOW",
            "MODIFIER",
        }:
            raise ValueError(f"Invalid consequence identity/impact: {term}")
        translations[term] = {
            **policy["consequence_labels"][term],
            "desc": fields["desc"],
            "impact": fields["impact"],
            "so_term": "SO:" + fields["acc"],
            "group": memberships[term],
        }
    groups = {
        group: [term for term in terms if term in translations]
        for group, terms in policy["consequence_groups"].items()
        if any(term in translations for term in terms)
    }
    return translations, groups


def variant_classes(text: str, policy: dict) -> dict:
    """Read the official SO variant-class table without importing example rows.

    Args:
        text: Release-specific classification HTML.
        policy: Reviewed application display labels.

    Returns:
        Class translations in the existing storage format.

    Raises:
        ValueError: A class is unreviewed, duplicated, or the table is missing.
    """
    result = {}
    for row in html_rows(text):
        if len(row) < 4 or not re.fullmatch(r"SO:\d{7}", row[3]):
            continue
        term = row[1]
        if term not in policy["variant_labels"] or term in result:
            raise ValueError(f"Unreviewed or duplicate variant class: {term}")
        result[term] = {**policy["variant_labels"][term], "desc": row[2], "so_term": row[3]}
    if len(result) < 20:
        raise ValueError("Missing or incomplete Ensembl variant-class table")
    return result


def cache_metadata(text: str, release: int) -> dict:
    """Read published human cache versions; absent entries remain empty strings.

    Args:
        text: Release-specific VEP cache documentation source.
        release: Major Ensembl release used to expand its version template marker.

    Returns:
        GRCh37/GRCh38 metadata; gnomAD retains separate exome/genome descriptions.

    Raises:
        ValueError: The human cache table or assembly identity is missing or inconsistent.
    """
    rows = html_rows(text)
    header = next(
        (
            i
            for i, row in enumerate(rows)
            if row == ["Source", "Version (GRCh38)", "Version (GRCh37)"]
        ),
        None,
    )
    if header is None:
        raise ValueError("Missing human cache version table")
    table = {}
    for row in rows[header + 1 :]:
        if len(row) != 3:
            break
        table[row[0]] = row[1:]
    fields = {
        "gencode": "GENCODE",
        "refseq": "RefSeq",
        "regulatory_build": "Regulatory build",
        "polyphen": "PolyPhen",
        "sift": "SIFT",
        "dbsnp": "dbSNP",
        "cosmic": "COSMIC",
        "hgmd_public": "HGMD-PUBLIC",
        "clinvar": "ClinVar",
        "1000_genomes": "1000 Genomes",
        "nhlbi_esp": "NHLBI-ESP",
    }
    result = {}
    for index, build in enumerate(("GRCh38", "GRCh37")):
        version = table.get("Ensembl database version", ["", ""])[index]
        if version not in (str(release), "[[SPECIESDEFS::ENSEMBL_VERSION]]"):
            raise ValueError(f"Cache release mismatch: {version}")
        assembly = table.get("Genome assembly", ["", ""])[index]
        if not assembly.startswith(build + ".p"):
            raise ValueError(f"Cache assembly mismatch: {assembly}")
        data = {key: table.get(label, ["", ""])[index] for key, label in fields.items()}
        if "PolyPhen-2" in table:
            data["polyphen"] = table["PolyPhen-2"][index]
        accessions = re.findall(r"(GCF_\d+\.\d+)_" + re.escape(assembly), data["refseq"])
        data.update(
            assembly_name=build,
            assembly_accession=accessions[0] if accessions else "",
            genome_assembly=assembly,
            genome_build=build,
            ensembl_version=release,
            gnomad="; ".join(
                f"{label}: {values[index]}"
                for label, values in table.items()
                if label.lower().startswith("gnomad")
            ),
        )
        # Preserve additional published sources without changing existing field meanings.
        data["published_sources"] = {label: values[index] for label, values in table.items()}
        data["published_sources"]["Ensembl database version"] = str(release)
        result[build] = data
    return result


def diagram_document(content: bytes, source_url: str, release: int) -> dict:
    """Validate a downloaded JPEG, PNG or restricted SVG diagram for storage.

    Args:
        content: Original image bytes, limited to two megabytes.
        source_url: Immutable Ensembl source URL for attribution.
        release: Major release owning this diagram.

    Returns:
        Base64 image data, MIME type, dimensions and SHA-256 provenance.

    Raises:
        ValueError: The image exceeds limits, has an unsupported format, or contains
            forbidden SVG elements, events, entities or external references.
        OSError: Image bytes cannot be decoded.
    """
    if len(content) > 2_000_000:
        raise ValueError("Ensembl diagram exceeds the image size limit")
    if source_url.endswith(".svg"):
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ValueError("SVG entity declarations are not allowed")
        root = ET.fromstring(content)
        allowed = {
            "svg",
            "g",
            "defs",
            "linearGradient",
            "stop",
            "path",
            "line",
            "polyline",
            "polygon",
            "rect",
            "circle",
            "ellipse",
            "text",
            "tspan",
            "title",
            "image",
        }
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] not in allowed:
                raise ValueError("Unsupported SVG element")
            for key, value in element.attrib.items():
                name = key.rsplit("}", 1)[-1].lower()
                if name.startswith("on") or (
                    name == "href" and not value.startswith(("#", "data:image/png;base64,"))
                ):
                    raise ValueError("External or executable SVG content is not allowed")
                if "url(" in value and re.search(r"url\(\s*[^#]", value):
                    raise ValueError("External SVG style reference is not allowed")
        width, height = (round(float(v)) for v in root.attrib["viewBox"].split()[-2:])
        if width <= 0 or height <= 0 or width * height > 20_000_000:
            raise ValueError("Unsupported diagram dimensions")
        return {
            "mime_type": "image/svg+xml",
            "data_base64": base64.b64encode(content).decode("ascii"),
            "width": width,
            "height": height,
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_url": source_url,
            "release": str(release),
        }
    with Image.open(io.BytesIO(content)) as image:
        if image.format not in ("JPEG", "PNG") or image.width * image.height > 20_000_000:
            raise ValueError("Unsupported Ensembl diagram format or dimensions")
        image.verify()
        return {
            "mime_type": Image.MIME[image.format],
            "data_base64": base64.b64encode(content).decode("ascii"),
            "width": image.width,
            "height": image.height,
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_url": source_url,
            "release": str(release),
        }


def fetch_diagram(release: int, sha: str) -> tuple[dict, bytes]:
    """Fetch the diagram linked by the release's own documentation page.

    Args:
        release: Major release being imported.
        sha: Pinned public-plugins Git commit.

    Returns:
        Validated diagram document and original image bytes.

    Raises:
        ValueError: The documentation does not identify exactly one supported diagram.
        httpx.HTTPError: The official source is unavailable.
    """
    base = f"https://raw.githubusercontent.com/Ensembl/public-plugins/{sha}/ensembl/htdocs/info/genome/variation/prediction/"
    with httpx.Client(timeout=60) as client:
        page = client.get(base + "predicted_data.html")
        page.raise_for_status()
        tree = tinyhtml5.parse(page.text, namespace_html_elements=False)
        names = {
            node.attrib.get("src")
            for node in tree.iter("img")
            if node.attrib.get("src")
            in {"consequences.jpg", "consequences.png", "consequences.svg"}
        }
        if len(names) != 1:
            raise ValueError("Missing or ambiguous consequence diagram")
        url = base + names.pop()
        response = client.get(url)
        response.raise_for_status()
        return diagram_document(response.content, url, release), response.content


def fetch_release(
    release: int, output: Path, policy: dict, actor: str, refs: dict
) -> tuple[dict, dict]:
    """Download pinned official sources and validate one release document.

    Args:
        release: Major Ensembl release, excluding the protected release 103.
        output: Directory for retained source files, one subdirectory per release.
        policy: Reviewed consequence grouping and labels.
        actor: Import provenance identity, not an application account credential.
        refs: Repository/major-release map of pinned official Git commit IDs.

    Returns:
        Validated document and manifest of immutable URLs and SHA-256 digests.

    Raises:
        ValueError: Release 103 is requested or downloaded definitions fail validation.
        httpx.HTTPError: An official source cannot be downloaded successfully.
    """
    if release == 103:
        raise ValueError("Release 103 is protected")
    folder = output / str(release)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with httpx.Client(
        timeout=60, follow_redirects=True, transport=httpx.HTTPTransport(retries=3)
    ) as client:
        sources = {}
        paths_by_repo = {"public-plugins": [CLASSIFICATION, CACHE]}
        # The website renderer moved from the plugin to webcode in release 100.
        if release < 100:
            paths_by_repo["public-plugins"].append("ensembl/" + CONSEQUENCES)
        else:
            paths_by_repo["ensembl-webcode"] = [CONSEQUENCES]
        for repo, paths in paths_by_repo.items():
            sha = refs[repo][release]
            for path in paths:
                url = f"https://raw.githubusercontent.com/Ensembl/{repo}/{sha}/{path}"
                response = client.get(url)
                response.raise_for_status()
                name = Path(path).name
                (folder / name).write_bytes(response.content)
                manifest[name] = {
                    "url": url,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
                sources[name] = response.text
    diagram, image_bytes = fetch_diagram(release, refs["public-plugins"][release])
    image_name = diagram["source_url"].rsplit("/", 1)[-1]
    (folder / image_name).write_bytes(image_bytes)
    manifest[image_name] = {"url": diagram["source_url"], "sha256": diagram["sha256"]}
    translations, groups = consequences(sources["ConsequenceTable.pm"], policy)
    document = {
        "vep_id": str(release),
        "created_by": actor,
        "created_on": datetime.now(UTC),
        **reference_links(release),
        "db_info": cache_metadata(sources["vep_cache.html"], release),
        "variant_class_translations": variant_classes(sources["classification.html"], policy),
        "conseq_translations": translations,
        "consequence_groups": groups,
        "consequence_diagram": diagram,
    }
    validated = VepMetadataDoc.model_validate(
        {**document, "consequence_diagram": split_diagram(diagram)[0]}
    ).model_dump(by_alias=True, exclude_none=True)
    # Download review output transports bytes; persistence always splits them out.
    validated["consequence_diagram"] = diagram
    return validated, manifest


def merge_seed(documents: list[dict], path: Path) -> None:
    """Replace downloaded releases in a seed while retaining all untouched records.

    Args:
        documents: Validated documents excluding protected release 103.
        path: Existing or new compressed NDJSON seed; replacement is atomic.

    Raises:
        ValueError: An input attempts to replace release 103.
    """
    if any(row["vep_id"] == "103" for row in documents):
        raise ValueError("Release 103 is protected")
    existing = {}
    if path.exists():
        with gzip.open(path, "rt") as stream:
            existing = {row["vep_id"]: row for row in map(json.loads, stream)}
    for row in documents:
        row = dict(row)
        if row.get("consequence_diagram"):
            row["consequence_diagram"] = seed_diagram(row["consequence_diagram"], path.parent)
        existing[row["vep_id"]] = VepMetadataDoc.model_validate(row).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    payload = "".join(
        json.dumps(existing[key], ensure_ascii=True) + "\n" for key in sorted(existing, key=int)
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(gzip.compress(payload.encode(), mtime=0))
    temporary.replace(path)


def install(collection, documents: list[dict], backup: Path) -> None:
    """Back up and atomically replace only the requested reference releases.

    Args:
        collection: Configured knowledgebase VEP collection with maintenance write access.
        documents: Validated major-release documents; never release 103.
        backup: New BSON file retaining original IDs and values of replaced documents.

    Raises:
        ValueError: An input requests protected release 103 or has duplicate IDs.
        RuntimeError: A concurrent writer changes records after the backup is taken.
        FileExistsError: The backup already exists.

    Notes:
        Requires a replica set. Preserves MongoDB IDs and does not touch samples,
        findings, annotation records, or stored reports. Pause reference writers first.
    """
    ids = [row["vep_id"] for row in documents]
    if "103" in ids or len(ids) != len(set(ids)):
        raise ValueError("Protected or duplicate release")
    for row in documents:
        validation_input = dict(row)
        if row.get("consequence_diagram"):
            validation_input["consequence_diagram"] = split_diagram(row["consequence_diagram"])[0]
        VepMetadataDoc.model_validate(validation_input)
    query = {"vep_id": {"$in": ids}}
    original = list(collection.find(query))
    with backup.open("xb") as stream:
        os.chmod(backup, 0o600)
        for row in original:
            stream.write(BSON.encode(row))

    def replace(session):
        """Verify the backup still matches and replace within one database transaction.

        Args:
            session: Transaction session belonging to the target collection's client.

        Raises:
            RuntimeError: Current records differ from the backed-up originals.
        """
        current = list(collection.find(query, session=session))
        if sorted(current, key=lambda row: row["vep_id"]) != sorted(
            original, key=lambda row: row["vep_id"]
        ):
            raise RuntimeError("Reference records changed after backup; rerun with a new backup")
        for row in documents:
            row = dict(row)
            if row.get("consequence_diagram"):
                row["consequence_diagram"] = store_diagram(
                    collection.database, row["consequence_diagram"], session
                )
            collection.replace_one({"vep_id": row["vep_id"]}, row, upsert=True, session=session)

    run_transaction(collection.database.client, replace)


def main() -> int:
    """Download and preview by default; explicitly opt into database or seed writes.

    Returns:
        Zero after all requested downloads, validation, and optional writes succeed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-release", type=int, default=98)
    parser.add_argument("--to-release", type=int, required=True)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--update-seed", action="store_true")
    args = parser.parse_args()
    if args.cpus < 1 or args.from_release < 98 or args.to_release < args.from_release:
        parser.error("Invalid release range or CPU count")
    if args.apply and not args.backup:
        parser.error("--apply requires --backup")
    policy = json.loads(POLICY.read_text())
    releases = [n for n in range(args.from_release, args.to_release + 1) if n != 103]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    refs = {}
    with httpx.Client(timeout=60) as client:
        for repo in ("ensembl-webcode", "public-plugins"):
            response = client.get(
                f"https://api.github.com/repos/Ensembl/{repo}/git/matching-refs/heads/release/"
            )
            response.raise_for_status()
            refs[repo] = {
                int(row["ref"].rsplit("/", 1)[1]): row["object"]["sha"]
                for row in response.json()
                if re.fullmatch(r"refs/heads/release/\d+", row["ref"])
            }
            missing = set(releases) - refs[repo].keys()
            if missing:
                raise ValueError(f"Missing official {repo} releases: {sorted(missing)}")
    with ThreadPoolExecutor(max_workers=args.cpus) as pool:
        futures = [
            pool.submit(fetch_release, n, args.output_dir, policy, args.actor, refs)
            for n in releases
        ]
        results = [future.result() for future in futures]
    documents = [document for document, _ in results]
    manifest = {document["vep_id"]: source for document, source in results}
    manifest["policy_sha256"] = hashlib.sha256(POLICY.read_bytes()).hexdigest()
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "documents.json").write_text(json_util.dumps(documents, indent=2) + "\n")
    for row in documents:
        print(
            f"release={row['vep_id']} classes={len(row['variant_class_translations'])} "
            f"consequences={len(row['conseq_translations'])} groups={len(row['consequence_groups'])}"
        )
    if args.apply:
        config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
        uri, database = config.get("KNOWLEDGEBASE_MONGO_URI"), config.get("KNOWLEDGEBASE_DB")
        if not uri or not database:
            parser.error("Set KNOWLEDGEBASE_MONGO_URI and KNOWLEDGEBASE_DB")
        with MongoClient(uri, serverSelectionTimeoutMS=10000) as client:
            name = load_collection_section("knowledgebase")["vep_metadata_collection"]
            install(client[database][name], documents, args.backup)
    if args.update_seed:
        merge_seed(documents, SEED)
        provenance_path = SEED.with_name("vep_metadata.sources.json")
        previous = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
        previous.update(manifest)
        provenance_path.write_text(json.dumps(previous, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
