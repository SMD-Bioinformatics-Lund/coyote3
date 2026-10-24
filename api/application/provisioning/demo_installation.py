"""Install packaged synthetic configuration and ingest explicitly selected demo manifests."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId

from api.application.provisioning.demo_catalog import DemoCatalogResources
from api.application.query_rules.service import QueryRuleService
from api.application.reporting.clinical_rules.validation import content_hash
from api.application.resources.release_compilation import compile_bundle_configurations
from api.config.constants import ALL_SAMPLE_FILE_KEYS
from api.contracts.demo_installation import DemoInstallationPlan, DemoSampleStatus
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error

BUNDLE = Path(__file__).resolve().parents[3] / "demo_data/clinical_workflows"
STARTER_SAMPLES = {
    "first_sample": ("DEMO_STARTER_DNA", "demo-hematology-training", "myeloid"),
    "rna_fusion": ("DEMO_STARTER_RNA", "demo-rna-training", "lymphoid"),
}
STARTER_CATALOG_ID = "c0de00000000000000000001"


class DemoInstallationService:
    """Coordinate the fixed server-owned demo bundle without accepting client file paths."""

    def __init__(
        self,
        repository: Any,
        ingest: Any,
        bundle: Path = BUNDLE,
        *,
        query_rule_service: QueryRuleService | None = None,
    ) -> None:
        """Bind storage, normal ingestion and source policy resolution.

        Args:
            repository: Demo installation and collision-check repository.
            ingest: Normal ingest service; None permits configuration planning only.
            bundle: Server-owned directory containing synthetic setup and raw manifests.
            query_rule_service: Deployment resolver for published policy ancestors. None
                compiles packaged policies over software defaults for offline fixture work.
        """
        self.repository = repository
        self.ingest = ingest
        self.bundle = bundle
        self.query_rule_service = query_rule_service or QueryRuleService(None)

    def configuration(self, actor: str) -> dict[str, list[dict[str, Any]]]:
        """Validate packaged configuration and attach installer identity and current timestamps.

        Args:
            actor: Authenticated operator username, or preview for a read-only plan.

        Returns:
            Current-schema synthetic records with published rules restricted to
            assays supplied by the selected demonstration package.

        Raises:
            AppError: Bundle is absent, a profile uses an unsupported environment,
                or a rule references an assay outside the bundle.
        """
        if not (self.bundle / "setup").is_dir():
            raise api_error(503, "This image does not contain the demonstration bundle")
        documents = {}
        now = datetime.now(timezone.utc)
        directory = self.bundle
        for path in sorted((directory / "setup").glob("*.json")):
            rows = []
            for source in json.loads(path.read_text()):
                row = normalize_collection_document(path.stem, source)
                row["_id"] = (
                    ObjectId(STARTER_CATALOG_ID)
                    if path.stem == "public_assay_catalog_versions"
                    else ObjectId()
                )
                row["system_installed"] = True
                for field in ("created_by", "updated_by"):
                    if field in row:
                        row[field] = actor
                for field in ("created_on", "updated_on", "created_at", "updated_at"):
                    if field in row:
                        row[field] = now
                for field in ("published_at", "published_on", "effective_from"):
                    if row.get(field) is not None:
                        row[field] = now
                if path.stem == "asp_configs" and row["environment"] not in {
                    "testing",
                    "production",
                }:
                    raise api_error(
                        422, "Demo profiles require a testing or production environment"
                    )
                if path.stem == "clinical_rule_sets":
                    demo_assays = {
                        item["asp_id"]
                        for item in json.loads(
                            (directory / "setup/assay_specific_panels.json").read_text()
                        )
                    }
                    if row["scope"]["asp_id"] not in demo_assays:
                        raise api_error(422, "Demo reporting rules must belong to a packaged assay")
                    row["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(row))
                rows.append(normalize_collection_document(path.stem, row))
            documents[path.stem] = rows
        compile_bundle_configurations(documents, self.query_rule_service.repository)
        group_path = (
            Path(__file__).resolve().parents[2]
            / "config/bootstrap/reference/assay_groups.seed.ndjson"
        )
        groups = [
            normalize_collection_document("assay_groups", json.loads(line))
            for line in group_path.read_text().splitlines()
            if line.strip()
        ]
        resources = DemoCatalogResources(documents, groups)
        for publication in documents.get("public_assay_catalog_versions", []):
            publication["catalog"] = resources.compile(publication["catalog"])
        return documents

    def manifests(self) -> dict[str, Path]:
        """Return allowlisted positive manifests; negative fixtures cannot be installed."""
        return {path.stem: path for path in sorted((self.bundle / "manifests").glob("*.yaml"))}

    def install_starter(
        self, actor: str, *, force: bool = False, created_by: str | None = None
    ) -> dict[str, Any]:
        """Install connected starter configuration and ingest DNA and RNA samples.

        Args:
            actor: Authenticated operator recorded in installation and ingest audits.
            force: Repair missing packaged configuration and refresh unreviewed system samples.
            created_by: Creation identity for automated deployment data; None uses actor.

        Returns:
            Sample installation status. A retry resumes ingest after committed configuration.

        Raises:
            AppError: A configuration identity conflicts or normal ingest fails.
        """
        creator = created_by or actor
        documents = self.configuration(creator)
        if not self.repository.configuration_installed(documents, require_packaged=True):
            if force:
                self.repository.repair_configuration(documents, actor)
            else:
                self.repository.install(documents, actor)
        results = [
            self.install_sample(key, actor, force=force, created_by=creator)
            for key in STARTER_SAMPLES
        ]
        return {
            "status": "already_installed"
            if all(row["status"] == "already_installed" for row in results)
            else "installed"
        }

    def plan(self) -> DemoInstallationPlan:
        """Return configuration counts and presence of samples without database writes."""
        documents = self.configuration("preview")
        starter_samples = []
        for key, (name, assay, diagnosis) in STARTER_SAMPLES.items():
            existing = self.repository.sample(name) or {}
            starter_samples.append(
                DemoSampleStatus(
                    key=key,
                    name=name,
                    installed=existing.get("asp_id") == assay
                    and existing.get("diagnosis_id") == diagnosis
                    and existing.get("environment") == "testing",
                )
            )
        samples = []
        for key, path in self.manifests().items():
            payload = self.ingest.parse_yaml_payload(path.read_text())
            samples.append(
                DemoSampleStatus(
                    key=key,
                    name=payload["name"],
                    installed=self.repository.sample(payload["name"]) is not None,
                )
            )
        return DemoInstallationPlan(
            starter_configuration={
                name: len(rows) for name, rows in self.configuration("preview").items()
            },
            configuration={name: len(rows) for name, rows in documents.items()},
            configuration_installed=self.repository.configuration_installed(documents),
            samples=samples,
            starter_samples=starter_samples,
            starter_installed=all(sample.installed for sample in starter_samples)
            and self.repository.configuration_installed(
                self.configuration("preview"), require_packaged=True
            ),
        )

    def install_configuration(self, actor: str) -> dict[str, Any]:
        """Install all bundled configuration atomically without replacing existing records."""
        self.repository.install(self.configuration(actor), actor)
        return {"status": "installed"}

    def install_sample(
        self, key: str, actor: str, *, force: bool = False, created_by: str | None = None
    ) -> dict[str, Any]:
        """Ingest one allowlisted synthetic sample through the normal transactional parser.

        Args:
            key: Manifest key from the installation plan, never a filesystem path.
            actor: Authenticated installer username for ingest provenance.
            force: Reingest an unreviewed system-owned starter sample; preserve all other samples.
            created_by: Initial submitter for automated deployment data; None uses actor.

        Returns:
            Installed or already_installed; existing samples are never updated.

        Raises:
            AppError: Unknown key, missing configuration, conflicting identity or unsafe resource.
        """
        starter = key in STARTER_SAMPLES
        path = (
            self.bundle / "starter/manifests" / f"{key}.yaml"
            if starter
            else self.manifests().get(key)
        )
        if path is None:
            raise api_error(404, "Unknown demo sample")
        if not self.repository.configuration_installed(
            self.configuration(actor), require_packaged=starter
        ):
            raise api_error(409, "Install demo configuration before its samples")
        payload = self.ingest.parse_yaml_payload(path.read_text())
        existing = self.repository.sample(payload["name"])
        if existing:
            if starter and (
                existing.get("environment") != "testing"
                or existing.get("diagnosis_id") != payload.get("diagnosis_id")
            ):
                raise api_error(409, "Starter sample scope conflicts; nothing replaced")
            if existing.get("asp_id") != payload.get("asp_id") or existing.get(
                "environment"
            ) not in {None, "testing"}:
                raise api_error(409, "Sample name belongs to another assay; nothing replaced")
            if not force or not starter or not self.repository.sample_reinstallable(existing):
                return {"status": "already_installed"}
        for field in ALL_SAMPLE_FILE_KEYS:
            if payload.get(field):
                resource = (path.parent / payload[field]).resolve()
                if not resource.is_relative_to(self.bundle.resolve()):
                    raise api_error(422, "Demo resource is outside the packaged bundle")
                payload[field] = str(resource)
        self.ingest.ingest_sample_bundle(
            payload,
            allow_update=bool(existing),
            ingested_by=created_by or actor,
            ingest_source="api",
        )
        return {"status": "installed"}
