"""Prepare and independently approve exact-content configuration promotion between environments."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

from coyote3.application.common.release_resources import assay_resource
from coyote3.contracts.configuration_profiles import ConfigurationPromotionRequest
from coyote3.contracts.schemas.assay import AspConfigDoc
from coyote3.domain.common.errors import api_error


def configuration_digest(document: dict) -> str:
    """Hash the exact reviewed configuration content using canonical scalar representations."""
    return sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: (
                (
                    value.replace(tzinfo=timezone.utc)
                    if value.tzinfo is None
                    else value.astimezone(timezone.utc)
                ).isoformat(timespec="milliseconds")
                if isinstance(value, datetime)
                else str(value)
            ),
        ).encode()
    ).hexdigest()


class ConfigurationPromotionService:
    """Keep promotion review independent from source authoring and sample reassignment."""

    def __init__(self, repository, configurations):
        """Bind promotion storage and exact configuration revision reads."""
        self.repository = repository
        self.configurations = configurations

    def list(self) -> list[dict]:
        """Return retained proposals and publication results for review."""
        return self.repository.list_promotions()

    def propose(self, request: ConfigurationPromotionRequest, *, actor: str) -> dict:
        """Capture immutable source content and target concurrency state for independent review."""
        source = self.configurations.get_aspc_revision_no_meta(request.source_id)
        if not source:
            raise api_error(404, "Source configuration revision not found")
        if source["environment"] == request.target_environment:
            raise api_error(422, "Promotion requires a different target environment")
        assay_resource(source)
        candidate = deepcopy(source)
        for key in ("_id", "retired_by", "retired_on", "retired_reason", "supersedes_id"):
            candidate.pop(key, None)
        candidate["environment"] = request.target_environment
        candidate["aspc_id"] = self.configurations.build_aspc_id(
            source["asp_id"], request.target_environment, source["diagnosis_id"]
        )
        target = self.repository.promotion_target(candidate["aspc_id"])
        version = int((target or {}).get("version", 0))
        candidate.update(
            version=version + 1,
            is_active=True,
            system_managed=False,
            system_installed=False,
            created_by=actor,
            created_on=datetime.now(timezone.utc),
            updated_by=actor,
            updated_on=None,
            supersedes_id=(target or {}).get("_id"),
        )
        for key in ("query_policy_release", "clinical_rule_release", "clinical_rule_base"):
            candidate.pop(key, None)
        candidate["promotion"] = {
            "source_id": request.source_id,
            "source_hash": configuration_digest(source),
            "source_environment": source["environment"],
            "evidence": request.evidence,
        }
        candidate = AspConfigDoc.model_validate(candidate).model_dump(mode="python", by_alias=True)
        candidate.pop("_id", None)
        document = {
            "source_id": request.source_id,
            "source_hash": configuration_digest(source),
            "candidate": candidate,
            "content_hash": configuration_digest(candidate),
            "expected_target_version": version,
            "evidence": request.evidence,
            "reason": request.reason,
            "created_by": actor,
            "created_on": datetime.now(timezone.utc),
            "status": "pending",
            "approved_by": None,
            "approved_on": None,
            "target_id": None,
        }
        return self.repository.create_promotion(document)

    def approve(self, identity: str, *, actor: str, content_hash: str, reason: str) -> dict:
        """Approve exact reviewed content; stale proposals never overwrite a newer target release."""
        proposal = self.repository.get_promotion(identity)
        if not proposal:
            raise api_error(404, "Configuration promotion not found")
        if proposal["created_by"] == actor:
            raise api_error(403, "Another authorized user must review this promotion")
        if proposal["status"] != "pending" or proposal["content_hash"] != content_hash:
            raise api_error(409, "Reload the pending promotion before approval")
        source = self.configurations.get_aspc_revision_no_meta(proposal["source_id"])
        if not source or configuration_digest(source) != proposal["source_hash"]:
            raise api_error(409, "The source release changed; prepare a new promotion")
        if configuration_digest(proposal["candidate"]) != content_hash:
            raise api_error(409, "Promotion content failed integrity validation")
        return self.repository.approve_promotion(proposal, actor=actor, reason=reason)
