"""Profile precedence, immutable publication and reviewed environment promotion boundaries."""

from copy import deepcopy
from types import SimpleNamespace

import mongomock
import pytest

from api.application.resources.configuration_profiles import (
    ConfigurationProfileService,
    compile_profile_rules,
    compile_profiles,
    prepare_profile_update,
    profile_hash,
)
from api.application.resources.configuration_promotions import ConfigurationPromotionService
from api.contracts.configuration_profiles import (
    ConfigurationProfileDraft,
    ConfigurationPromotionRequest,
)
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.configuration_profiles import ConfigurationProfileRepository
from scripts.quality.export_demo_workflows import replay


@pytest.fixture
def profiles(monkeypatch):
    """Exercise real repositories in memory; transaction rollback has separate integration coverage."""
    import api.infra.mongo.repositories.configuration_profiles as module

    db = mongomock.MongoClient().governance
    adapter = SimpleNamespace(
        configuration_profiles_collection=db.profiles,
        configuration_promotions_collection=db.promotions,
        aspc_collection=db.configs,
        asp_collection=db.assays,
        assay_groups_collection=db.groups,
        diagnoses_collection=db.diagnoses,
    )
    monkeypatch.setattr(module, "run_transaction", lambda client, operation: operation(None))
    monkeypatch.setattr(module, "enqueue_audit", lambda *args, **kwargs: None)
    repository = ConfigurationProfileRepository(adapter)
    repository.ensure_indexes()
    db.groups.insert_one({"group_id": "solid", "is_active": True})
    return ConfigurationProfileService(repository), repository, db, adapter


def draft(**changes):
    """Build a synthetic partial SNV profile."""
    return ConfigurationProfileDraft.model_validate(
        {
            "profile_id": "solid_depth",
            "name": "Solid depth",
            "kind": "filters",
            "bindings": [{"asp_group": "solid"}],
            "content": {"somatic": {"snv": {"min_depth": 80}}},
            "reason": "Validated synthetic depth thresholds",
            **changes,
        }
    )


def test_profile_publication_requires_another_reviewer_and_exact_hash(profiles):
    service, repository, db, _ = profiles
    document = service.create(draft(), actor="author")
    identity = str(document["_id"])
    assert repository.published() == []
    with pytest.raises(AppError, match="Another authorized"):
        service.publish(
            identity, actor="author", content_hash=document["content_hash"], reason="Reviewed"
        )
    with pytest.raises(AppError, match="current draft"):
        service.publish(identity, actor="reviewer", content_hash="0" * 64, reason="Reviewed")
    published = service.publish(
        identity, actor="reviewer", content_hash=document["content_hash"], reason="Validated"
    )
    assert published["status"] == "published"
    assert published["published_by"] == "reviewer"
    newer = service.create(draft(content={"somatic": {"snv": {"min_depth": 90}}}), actor="author")
    assert repository.published()[0]["version"] == 1
    service.publish(
        str(newer["_id"]), actor="reviewer", content_hash=newer["content_hash"], reason="Validated"
    )
    assert repository.published()[0]["version"] == 2
    assert db.profiles.count_documents({}) == 2


def test_profile_precedence_and_explicit_empty_list_override(profiles):
    service, repository, _, _ = profiles
    for profile in (
        draft(content={"somatic": {"snv": {"min_depth": 50, "exclude_flags": ["LowQual"]}}}),
        draft(
            profile_id="solid_testing",
            bindings=[{"asp_group": "solid", "environment": "testing"}],
            content={"somatic": {"snv": {"min_depth": 80}}},
        ),
        draft(
            profile_id="solid_production",
            bindings=[{"asp_group": "solid", "environment": "production"}],
            content={"somatic": {"snv": {"min_depth": 120}}},
        ),
    ):
        row = service.create(profile, actor="author")
        service.publish(
            str(row["_id"]), actor="reviewer", content_hash=row["content_hash"], reason="Validated"
        )
    panel = {
        "asp_group": "solid",
        "asp_id": "demo-solid_gmsv3",
        "asp_category": "dna",
        "asp_family": "panel-dna",
    }
    configuration = {
        "diagnosis_id": "breast",
        "environment": "testing",
        "filters": {"somatic": {"snv": {"exclude_flags": []}}},
    }
    compile_profiles(configuration, panel, repository)
    assert configuration["filters"]["somatic"]["snv"] == {"min_depth": 80, "exclude_flags": []}
    assert [source["profile_id"] for source in configuration["profile_sources"]] == [
        "solid_depth",
        "solid_testing",
    ]


def test_duplicate_binding_and_changed_source_content_fail_compilation(profiles):
    service, repository, db, _ = profiles
    for identity in ("first", "second"):
        row = service.create(draft(profile_id=identity), actor="author")
        service.publish(
            str(row["_id"]), actor="reviewer", content_hash=row["content_hash"], reason="Validated"
        )
    panel = {"asp_group": "solid", "asp_id": "a", "asp_category": "dna", "asp_family": "panel-dna"}
    config = {"diagnosis_id": "base", "environment": "testing"}
    with pytest.raises(AppError, match="same binding rank"):
        compile_profiles(config, panel, repository)
    db.profiles.update_one({"profile_id": "first"}, {"$set": {"content": {}}})
    with pytest.raises(AppError, match="integrity"):
        compile_profiles(config, panel, repository)


def test_template_profile_records_the_installed_layout_hash(profiles):
    service, _, _, _ = profiles
    row = service.create(
        draft(kind="template", content={"template_name": "dna_report.html"}), actor="author"
    )
    assert len(row["content"]["content_hash"]) == 64
    assert row["content_hash"] == profile_hash(row)


def test_edit_preserves_authored_overrides_without_freezing_inherited_defaults():
    previous = {
        "filters": {"somatic": {"snv": {"min_depth": 80, "exclude_flags": []}}},
        "profile_sources": [{"profile_id": "depth"}],
        "profile_overrides": {"filters": {"somatic": {"snv": {"exclude_flags": []}}}},
    }
    submitted = deepcopy(previous)
    updated = deepcopy(previous)
    prepare_profile_update(previous, submitted, updated)
    assert updated["filters"] == {"somatic": {"snv": {"exclude_flags": []}}}
    submitted["filters"]["somatic"]["snv"]["min_depth"] = 90
    prepare_profile_update(previous, submitted, updated)
    assert updated["filters"]["somatic"]["snv"] == {"min_depth": 90, "exclude_flags": []}


@pytest.fixture
def promotion(profiles):
    _, repository, db, adapter = profiles
    source_db = replay()
    sample = source_db.samples.find_one({"name": "DEMO_FUSION"})
    source = source_db.asp_configs.find_one({"_id": sample["current_aspc_id"]})
    db.configs.insert_one(deepcopy(source))
    configs = ASPConfigRepository(adapter)
    configs.ensure_indexes()
    service = ConfigurationPromotionService(repository, configs)
    request = ConfigurationPromotionRequest(
        source_id=str(source["_id"]),
        target_environment="validation",
        evidence=["synthetic-validation-2026"],
        reason="Validated synthetic workflow",
    )
    return service, repository, db, source, request


def test_promotion_retains_source_and_requires_independent_review(promotion):
    service, _, db, source, request = promotion
    proposal = service.propose(request, actor="author")
    assert db.configs.count_documents({}) == 1
    with pytest.raises(AppError, match="Another authorized"):
        service.approve(
            str(proposal["_id"]),
            actor="author",
            content_hash=proposal["content_hash"],
            reason="Reviewed",
        )
    approved = service.approve(
        str(proposal["_id"]),
        actor="reviewer",
        content_hash=proposal["content_hash"],
        reason="Validated",
    )
    assert approved["status"] == "approved"
    target = db.configs.find_one({"environment": "validation"})
    assert target["promotion"]["source_id"] == str(source["_id"])
    assert (
        target["query_policy_release"]["policies"]["somatic.fusion"]["scope"]["environment"]
        == "validation"
    )
    assert db.configs.find_one({"_id": source["_id"]}) == source
    assert db.samples.count_documents({}) == 0


def test_stale_promotion_cannot_overwrite_an_approved_target(promotion):
    service, _, db, _, request = promotion
    first = service.propose(request, actor="author")
    stale = service.propose(request, actor="author")
    service.approve(
        str(first["_id"]), actor="reviewer", content_hash=first["content_hash"], reason="Validated"
    )
    with pytest.raises(AppError, match="target configuration changed"):
        service.approve(
            str(stale["_id"]),
            actor="reviewer",
            content_hash=stale["content_hash"],
            reason="Validated",
        )
    assert db.configs.count_documents({"environment": "validation"}) == 1


def test_changed_promotion_candidate_is_rejected_before_publication(promotion):
    service, _, db, _, request = promotion
    proposal = service.propose(request, actor="author")
    db.promotions.update_one(
        {"_id": proposal["_id"]}, {"$set": {"candidate.display_name": "Unreviewed change"}}
    )
    with pytest.raises(AppError, match="integrity"):
        service.approve(
            str(proposal["_id"]),
            actor="reviewer",
            content_hash=proposal["content_hash"],
            reason="Reviewed",
        )
    assert db.configs.count_documents({}) == 1


def test_clinical_profile_replaces_only_the_selected_block_and_retains_base(promotion):
    _, _, _, source, _ = promotion
    config = deepcopy(source)
    base = deepcopy(config["clinical_rule_release"])
    block = deepcopy(base["blocks"][0])
    block["rules"][0]["output"][0]["value"] = "Synthetic reviewed reporting text."
    config["profile_sources"] = [{"kind": "clinical_rules", "content": {"replace_blocks": [block]}}]
    with pytest.raises(AppError, match="failed validation"):
        compile_profile_rules(config)
    case = deepcopy(base["test_cases"][0])
    case["expected_sections"] = {"Report summary": ["Synthetic reviewed reporting text."]}
    config["profile_sources"][0]["content"]["replace_tests"] = [case]
    compile_profile_rules(config)
    assert config["clinical_rule_base"] == base
    assert config["clinical_rule_release"]["blocks"][0] == block
    assert config["clinical_rule_release"]["content_hash"] != base["content_hash"]
    config["profile_sources"][0]["content"] = {"disable_blocks": ["unknown"]}
    with pytest.raises(AppError, match="unknown block"):
        compile_profile_rules(config)
