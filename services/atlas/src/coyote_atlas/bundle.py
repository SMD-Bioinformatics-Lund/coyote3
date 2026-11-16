# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Read checked HGNC/VEP resources without a server, database or network connection."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from coyote.contracts.schemas.reference import HgncGenesDoc
from coyote.contracts.schemas.variant_annotations import VepDiagramAssetDoc, VepMetadataDoc

from coyote_atlas.models import BundleManifest, InstallationPlan


class ReferenceBundle:
    """An explicit reference directory whose inventory and collection contracts are checked."""

    def __init__(self, directory: Path) -> None:
        """Select local reference resources without loading environment configuration.

        Args:
            directory: Directory containing manifest.json and its inventoried resources.
        """
        self.directory = Path(directory).resolve()

    @classmethod
    def packaged(cls) -> ReferenceBundle:
        """Select the reference resources installed with this distribution.

        Returns:
            A bundle pointing inside the installed package, independent of the working directory.
        """
        return cls(Path(__file__).parent / "data" / "reference")

    def _manifest(self) -> tuple[BundleManifest, str]:
        """Parse the inventory and calculate its exact identity.

        Returns:
            Typed manifest and SHA-256 of the manifest bytes.

        Raises:
            OSError: The manifest cannot be read.
            ValueError: The manifest fails its schema.
        """
        content = (self.directory / "manifest.json").read_bytes()
        return BundleManifest.model_validate_json(content), hashlib.sha256(content).hexdigest()

    def inspect(self) -> BundleManifest:
        """Read source metadata without loading the large datasets.

        Returns:
            The parsed manifest; use validate before trusting its file claims.

        Raises:
            OSError: The manifest cannot be read.
            ValueError: The manifest fails its schema.
        """
        return self._manifest()[0]

    def _checked_files(self, manifest: BundleManifest) -> dict[str, bytes]:
        """Read exactly the inventory and verify each resource before parsing it.

        Args:
            manifest: Parsed, internally consistent reference inventory.

        Returns:
            Resource names mapped to verified bytes.

        Raises:
            OSError: An inventoried file cannot be read.
            ValueError: Resources escape the directory, are untracked or differ from the inventory.
        """
        expected = {entry.path for entry in manifest.files} | {"manifest.json"}
        actual = {
            path.relative_to(self.directory).as_posix()
            for path in self.directory.rglob("*")
            if path.is_file()
        }
        if actual != expected:
            raise ValueError("Reference directory does not match the manifest inventory")
        result = {}
        for entry in manifest.files:
            path = (self.directory / entry.path).resolve()
            if not path.is_relative_to(self.directory):
                raise ValueError("Reference resource escapes the bundle directory")
            content = path.read_bytes()
            if (
                len(content) != entry.size_bytes
                or hashlib.sha256(content).hexdigest() != entry.sha256
            ):
                raise ValueError(f"Reference resource checksum mismatch: {entry.path}")
            result[entry.path] = content
        return result

    def _load(self) -> tuple[InstallationPlan, dict[str, list[dict]], list[dict]]:
        """Validate files, collection records and referenced diagrams as one bundle.

        Returns:
            The pinned plan, unchanged decoded snapshot records and validated binary diagrams.

        Raises:
            OSError: An inventoried resource is missing, unreadable or invalid gzip.
            ValueError: Integrity, JSON, counts, identities or core collection validation fails.
        """
        manifest, digest = self._manifest()
        files = self._checked_files(manifest)
        models = {"hgnc_genes": HgncGenesDoc, "vep_metadata": VepMetadataDoc}
        keys = {"hgnc_genes": "hgnc_id", "vep_metadata": "vep_id"}
        documents = {}
        for dataset in manifest.datasets:
            rows = [
                json.loads(line)
                for line in gzip.decompress(files[dataset.path]).decode("utf-8").splitlines()
                if line.strip()
            ]
            identities = set()
            for row in rows:
                validated = models[dataset.dataset_id].model_validate(row)
                identity = getattr(validated, keys[dataset.dataset_id])
                if identity in identities:
                    raise ValueError(f"Duplicate reference identity in {dataset.dataset_id}")
                identities.add(identity)
            if len(rows) != dataset.records:
                raise ValueError(f"Reference record count mismatch: {dataset.dataset_id}")
            documents[dataset.dataset_id] = rows
        diagrams = {}
        for row in documents["vep_metadata"]:
            descriptor = row.get("consequence_diagram")
            if descriptor:
                asset_id = descriptor["sha256"]
                path = "vep_diagrams/" + asset_id
                if path not in files:
                    raise ValueError("VEP metadata references an untracked diagram")
                diagrams[asset_id] = VepDiagramAssetDoc.model_validate(
                    {"_id": asset_id, "data": files[path], "mime_type": descriptor["mime_type"]}
                ).model_dump(by_alias=True)
        if {path for path in files if path.startswith("vep_diagrams/")} != {
            "vep_diagrams/" + key for key in diagrams
        }:
            raise ValueError("Bundle contains an unreferenced VEP diagram")
        counts = {name: len(rows) for name, rows in documents.items()}
        counts["vep_diagrams"] = len(diagrams)
        plan = InstallationPlan(
            bundle_id=manifest.bundle_id,
            bundle_version=manifest.bundle_version,
            manifest_sha256=digest,
            datasets=manifest.datasets,
            collections=counts,
        )
        return plan, documents, list(diagrams.values())

    def validate(self) -> InstallationPlan:
        """Verify all files and clinical reference contracts without writing or connecting.

        Returns:
            Bundle identity and validated record counts, also used as an installation plan.

        Raises:
            OSError: A resource cannot be read or decompressed.
            ValueError: Integrity, record counts or collection contracts are invalid.
        """
        return self._load()[0]

    def plan(self) -> InstallationPlan:
        """Create an offline plan; target occupancy and authorization belong to the host.

        Returns:
            A validated plan pinned to this manifest's SHA-256.

        Raises:
            OSError: A resource cannot be read or decompressed.
            ValueError: Integrity or collection contracts are invalid.
        """
        return self.validate()

    def load_documents(self) -> dict[str, list[dict]]:
        """Return checked HGNC/VEP records for the host's existing provenance normalization.

        Returns:
            Fresh records preserving snapshot values; the host stamps installation provenance.

        Raises:
            OSError: A resource cannot be read or decompressed.
            ValueError: Integrity or collection contracts are invalid.
        """
        return self._load()[1]

    def load_diagrams(self) -> list[dict]:
        """Return verified diagrams using the existing core binary document contract.

        Returns:
            Content-addressed diagram documents with native bytes, not base64 strings.

        Raises:
            OSError: A resource cannot be read or decompressed.
            ValueError: Integrity or collection contracts are invalid.
        """
        return self._load()[2]
