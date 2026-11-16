# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Create an explicit review copy without mutating installed reference resources."""

import gzip
import hashlib
import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from coyote_atlas.bundle import ReferenceBundle


@contextmanager
def draft_bundle(output: Path, version: str) -> Iterator[Path]:
    """Copy packaged data, then regenerate and validate a maintainer's changed inventory.

    Args:
        output: New directory receiving the copy; existing directories are rejected.
        version: Explicit new bundle version, distinct from the installed version.

    Yields:
        The new reference directory where the caller may update reviewed resources.

    Raises:
        ValueError: Version is blank/unchanged, or the completed reference pack is invalid.
        FileExistsError: The output directory already exists.
        OSError: Reference files cannot be copied, read or written.

    Notes:
        Never changes installed package files or a database. An exception leaves the
        output copy for inspection; it is not a publishable artifact until validation passes.
        Unreferenced diagram assets are removed only from this new copy.
    """
    bundle = ReferenceBundle.packaged()
    bundle.validate()
    manifest = bundle.inspect().model_dump(mode="json")
    if not version.strip() or version.strip() == manifest["bundle_version"]:
        raise ValueError("Choose a new nonblank reference-bundle version")
    shutil.copytree(bundle.directory, output)
    yield output
    with gzip.open(output / "vep_metadata.seed.ndjson.gz", "rt") as stream:
        vep = list(map(json.loads, stream))
    diagram_ids = {
        row["consequence_diagram"]["sha256"] for row in vep if row.get("consequence_diagram")
    }
    for path in (output / "vep_diagrams").iterdir():
        if path.name not in diagram_ids:
            path.unlink()
    for dataset in manifest["datasets"]:
        content = (output / dataset["path"]).read_bytes()
        dataset["version"] = "sha256:" + hashlib.sha256(content).hexdigest()
        dataset["records"] = sum(
            bool(line.strip()) for line in gzip.decompress(content).splitlines()
        )
        if dataset["dataset_id"] == "vep_metadata":
            dataset["source"]["upstream_version"] = ",".join(
                sorted((row["vep_id"] for row in vep), key=int)
            )
    manifest["bundle_version"] = version.strip()
    manifest["files"] = [
        {
            "path": path.relative_to(output).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    ReferenceBundle(output).validate()
