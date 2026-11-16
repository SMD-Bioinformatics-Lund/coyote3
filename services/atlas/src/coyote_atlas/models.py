# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Integrity and provenance contracts for an offline reference bundle."""

from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BundleFile(BaseModel):
    """A bundled resource identified by its relative path and exact byte digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        """Require a canonical relative POSIX path inside the reference directory.

        Args:
            value: Manifest resource name, without a leading slash or traversal.

        Returns:
            The unchanged resource name.

        Raises:
            ValueError: The path is empty, absolute, noncanonical or traverses a parent.
        """
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or str(path) != value
            or "\\" in value
            or value == "."
        ):
            raise ValueError("Bundle paths must remain inside the reference directory")
        return value


class DatasetSource(BaseModel):
    """Retained source evidence without inventing an upstream release or acquisition date."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(min_length=1)
    description: str = Field(min_length=1)
    upstream_version: str | None = None
    provenance_files: tuple[str, ...] = ()
    notice_files: tuple[str, ...] = ()


class Dataset(BaseModel):
    """One collection snapshot and its independently identified dataset version."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    dataset_id: Literal["hgnc_genes", "vep_metadata"]
    version: str = Field(min_length=1)
    path: str
    records: int = Field(gt=0)
    source: DatasetSource


class BundleManifest(BaseModel):
    """Complete file inventory and source identities of a packaged reference release."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    format_version: Literal[1]
    bundle_id: str = Field(min_length=1)
    bundle_version: str = Field(min_length=1)
    datasets: tuple[Dataset, ...]
    files: tuple[BundleFile, ...]

    @model_validator(mode="after")
    def complete_inventory(self):
        """Require unique files and both snapshots with tracked provenance resources.

        Returns:
            This validated manifest.

        Raises:
            ValueError: A dataset/file is duplicate, missing or references an untracked resource.
        """
        paths = {entry.path for entry in self.files}
        identities = [dataset.dataset_id for dataset in self.datasets]
        if len(paths) != len(self.files) or "manifest.json" in paths:
            raise ValueError("Bundle file inventory contains duplicate or reserved paths")
        if sorted(identities) != ["hgnc_genes", "vep_metadata"]:
            raise ValueError("A bundle requires one HGNC and one VEP dataset")
        if len({dataset.path for dataset in self.datasets}) != len(self.datasets):
            raise ValueError("Each dataset requires a distinct resource")
        for dataset in self.datasets:
            required = {
                dataset.path,
                *dataset.source.provenance_files,
                *dataset.source.notice_files,
            }
            if not required <= paths or not dataset.path.endswith(".ndjson.gz"):
                raise ValueError("Dataset and provenance resources must be inventoried")
        return self


class InstallationPlan(BaseModel):
    """A validated bundle identity reviewed before the host decides whether to write."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    bundle_id: str
    bundle_version: str
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    datasets: tuple[Dataset, ...]
    collections: dict[str, int]
