"""Contracts for authenticated installation of bundled deployment data."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DeploymentDataScope = Literal["identity", "application", "knowledgebase", "all"]
DeploymentDataModule = Literal["identity", "application", "knowledgebase", "demo"]


class DeploymentDataRequest(BaseModel):
    """Select packaged deployment catalogs; client paths and installer identities are forbidden."""

    model_config = ConfigDict(extra="forbid")
    modules: list[DeploymentDataModule] = Field(min_length=1)
    force: bool = False

    @field_validator("modules")
    @classmethod
    def unique_modules(cls, modules: list[DeploymentDataModule]) -> list[DeploymentDataModule]:
        """Reject repeated module selection rather than running a reinstall twice."""
        if len(set(modules)) != len(modules):
            raise ValueError("Select each module once")
        return modules


class DeploymentDataResult(BaseModel):
    """Collection-level load/skip results without exposing database connection details."""

    collections: dict[
        str,
        Literal[
            "loaded", "skipped", "empty", "repaired", "preserved", "installed", "already_installed"
        ],
    ]
