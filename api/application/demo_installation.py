"""Install packaged synthetic configuration and ingest explicitly selected demo manifests."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId

from api.application.reporting.clinical_rules.validation import content_hash
from api.config.constants import ALL_SAMPLE_FILE_KEYS
from api.contracts.demo_installation import DemoInstallationPlan, DemoSampleStatus
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error

BUNDLE = Path(__file__).resolve().parents[2] / "demo_data/clinical_workflows"


class DemoInstallationService:
    """Coordinate the fixed server-owned demo bundle without accepting client file paths."""

    def __init__(self, repository: Any, ingest: Any, bundle: Path = BUNDLE) -> None:
        """Bind application storage, the normal ingest service and packaged fixture root."""
        self.repository = repository
        self.ingest = ingest
        self.bundle = bundle

    def configuration(self, actor: str) -> dict[str, list[dict]]:
        """Validate packaged configuration and attach installer identity and current timestamps.

        Args:
            actor: Authenticated operator username, or preview for a read-only plan.

        Returns:
            Current-schema synthetic records; reporting rules remain unpublished drafts.

        Raises:
            AppError: Demo bundle is absent or contains a non-testing profile or published rule.
        """
        if not (self.bundle / "setup").is_dir():
            raise api_error(503, "This image does not contain the demonstration bundle")
        documents = {}
        now = datetime.now(timezone.utc)
        for path in sorted((self.bundle / "setup").glob("*.json")):
            rows = []
            for source in json.loads(path.read_text()):
                row = normalize_collection_document(path.stem, source)
                row["_id"] = ObjectId()
                for field in ("created_by", "updated_by"):
                    if field in row:
                        row[field] = actor
                for field in ("created_on", "updated_on", "created_at", "updated_at"):
                    if field in row:
                        row[field] = now
                if path.stem == "asp_configs" and row["environment"] != "testing":
                    raise api_error(422, "Demo profiles must use the testing environment")
                if path.stem == "clinical_rule_sets":
                    if row["status"] != "draft" or row.get("active"):
                        raise api_error(422, "Demo reporting rules must be inactive drafts")
                    row["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(row))
                rows.append(normalize_collection_document(path.stem, row))
            documents[path.stem] = rows
        return documents

    def manifests(self) -> dict[str, Path]:
        """Return allowlisted positive manifests; negative fixtures cannot be installed."""
        return {path.stem: path for path in sorted((self.bundle / "manifests").glob("*.yaml"))}

    def plan(self) -> DemoInstallationPlan:
        """Return configuration counts and presence of samples without database writes."""
        documents = self.configuration("preview")
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
            configuration={name: len(rows) for name, rows in documents.items()},
            configuration_installed=self.repository.configuration_installed(documents),
            samples=samples,
        )

    def install_configuration(self, actor: str) -> dict:
        """Install all bundled configuration atomically without replacing existing records."""
        self.repository.install(self.configuration(actor), actor)
        return {"status": "installed"}

    def install_sample(self, key: str, actor: str) -> dict:
        """Ingest one allowlisted synthetic sample through the normal transactional parser.

        Args:
            key: Manifest key from the installation plan, never a filesystem path.
            actor: Authenticated installer username for ingest provenance.

        Returns:
            Installed or already_installed; existing samples are never updated.

        Raises:
            AppError: Unknown key, missing configuration, conflicting identity or unsafe resource.
        """
        path = self.manifests().get(key)
        if path is None:
            raise api_error(404, "Unknown demo sample")
        if not self.repository.configuration_installed(self.configuration(actor)):
            raise api_error(409, "Install demo configuration before its samples")
        payload = self.ingest.parse_yaml_payload(path.read_text())
        existing = self.repository.sample(payload["name"])
        if existing:
            if existing.get("asp_id") != payload.get("asp_id"):
                raise api_error(409, "Sample name belongs to another assay; nothing replaced")
            return {"status": "already_installed"}
        for field in ALL_SAMPLE_FILE_KEYS:
            if payload.get(field):
                resource = (path.parent / payload[field]).resolve()
                if not resource.is_relative_to(self.bundle.resolve()):
                    raise api_error(422, "Demo resource is outside the packaged bundle")
                payload[field] = str(resource)
        self.ingest.ingest_sample_bundle(payload, ingested_by=actor, ingest_source="api")
        return {"status": "installed"}
