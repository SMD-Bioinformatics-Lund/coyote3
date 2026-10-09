"""Validate installed policies and upgrade planning against synthetic Mongo storage."""

import json
import re
from copy import deepcopy
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pytest

from api.application.query_rules import QueryRuleService
from api.config.clinical_query_policy import CLINICAL_QUERY_POLICY, resolved_query_policy
from api.domain.core.dna.varqueries import _exception_clause
from api.infra.mongo.repositories.query_rules import QueryRuleRepository
from scripts.bootstrap import install_query_rules
from scripts.bootstrap.query_rule_seed import prepare_query_rule_seeds

ROOT = Path(__file__).resolve().parents[2]


def seed_rows(name):
    """Read public reference records without connecting to a deployment."""
    path = ROOT / f"api/config/bootstrap/reference/{name}.seed.ndjson"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_installed_germline_rules_are_group_scoped():
    rows = prepare_query_rule_seeds(
        seed_rows("query_rule_sets"), seed_rows("assay_groups"), actor="installer"
    )
    db = mongomock.MongoClient().synthetic
    db.query_rule_sets.insert_many(rows)
    service = QueryRuleService(
        QueryRuleRepository(
            SimpleNamespace(
                query_rule_sets_collection=db.query_rule_sets,
                query_rule_revisions_collection=db.query_rule_revisions,
            )
        )
    )
    from api.contracts.schemas.query_rules import QueryRuleScope

    for group in ("hematology", "myeloid", "tumwgs"):
        policy = service.resolve(QueryRuleScope(assay_group=group, analysis="snv"))
        assert policy.evidence_mode == "paired"
        assert {e["id"] for e in policy.exceptions} == {
            "flt3_svtype",
            "flt3_large_insertion",
            "germline__germline_myeloid_marker",
            "germline__germline_cebpa_filter",
            "germline__germline_chr1_interval",
        }
    inherited = service.resolve(
        QueryRuleScope(assay_group="future_group", analysis="snv", intent="germline")
    )
    assert inherited.evidence_mode == "exception_only"
    assert inherited.exceptions == []
    solid = service.resolve(QueryRuleScope(assay_group="solid", analysis="snv", intent="germline"))
    assert {e["id"] for e in solid.exceptions} == {"solid_germline_filter"}
    for group in ("lymphoid", "wts", "demo"):
        assert (
            service.resolve(
                QueryRuleScope(assay_group=group, analysis="snv", intent="germline")
            ).exceptions
            == []
        )
    assert not any(row["scope"].get("assay_group") is None for row in rows)
    assert not CLINICAL_QUERY_POLICY.snv.exceptions
    for row in rows:
        assert row["system_installed"] and row["version"] == row["revision"] == 1
        assert row["created_by"] == row["updated_by"] == row["published_by"] == "installer"
        assert not row.get("approved_by")
        assert all(set(e) == {"id", "mode", "condition"} for e in row["content"]["exceptions"])


@pytest.mark.parametrize("with_demo", [False, True])
def test_fresh_bootstrap_loads_complete_query_catalog(with_demo):
    """First installation includes catalog-only rules as well as TOML criteria."""
    from api.contracts.schemas.query_rules import QueryRuleContent
    from scripts.bootstrap.bootstrap_database import (
        DEFAULT_DEMO_CENTER_DIR,
        DEFAULT_RBAC_DIR,
        DEFAULT_REFERENCE_DIR,
        _build_seed_documents,
    )

    seed = _build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        demo_center_dir=DEFAULT_DEMO_CENTER_DIR if with_demo else None,
        actor="installer",
        include_knowledgebase=False,
    )
    expected = prepare_query_rule_seeds(
        seed_rows("query_rule_sets"), seed_rows("assay_groups"), actor="installer"
    )
    actual = {row["query_id"]: row["content"] for row in seed["query_rule_sets"]}
    assert len(actual) == 8
    assert actual == {
        row["query_id"]: QueryRuleContent.model_validate(row["content"]).model_dump()
        for row in expected
    }
    assert len(seed["roles"]) == 31
    assert len(seed["assay_groups"]) == 9
    assert len(seed.get("subpanels", [])) == (1 if with_demo else 0)
    assert "hgnc_genes" not in seed


def test_installed_trees_preserve_legacy_matching_and_condition_order():
    """Convert shipped criteria without changing matches for valid ASCII VCF alleles."""
    legacy = {
        "flt3_svtype": {"genes": ["FLT3"], "info_fields_present": ["SVTYPE"]},
        "flt3_large_insertion": {"genes": ["FLT3"], "alt_regex": r"\w{10,200}"},
        "solid_regulatory_tert_nfkbie": {
            "genes": ["TERT", "NFKBIE"],
            "consequence_terms": ["regulatory_region_variant", "TF_binding_site_variant"],
        },
        "germline_myeloid_marker": {"info_equals": {"MYELOID_GERMLINE": 1}},
        "germline_cebpa_filter": {"genes": ["CEBPA"], "filter_values": ["GERMLINE"]},
        "germline_chr1_interval": {
            "chromosomes": ["1"],
            "position_min": 115256521,
            "position_max": 115256537,
        },
        "solid_germline_filter": {"filter_values": ["GERMLINE"]},
    }
    documents = []
    for gene in ["FLT3", "TERT", "NFKBIE", "CEBPA", "OTHER"]:
        for alt in ["A", "A" * 9, "A" * 10, "a" * 200, "A" * 201, "<DUP>"]:
            for pos in [115256520, 115256521, 115256537, 115256538]:
                documents.append(
                    {
                        "INFO": {
                            "selected_CSQ": {"SYMBOL": gene},
                            "SVTYPE": "INS",
                            "MYELOID_GERMLINE": 1,
                        },
                        "ALT": alt,
                        "CHROM": "1",
                        "POS": pos,
                        "consequence_terms": ["regulatory_region_variant"],
                        "FILTER": ["GERMLINE"],
                    }
                )
    documents.extend([{}, {"INFO": {}}, {"INFO": {"MYELOID_GERMLINE": 0}}, {"CHROM": "2"}])
    collection = mongomock.MongoClient().synthetic.variants
    collection.insert_many(documents)
    rows = prepare_query_rule_seeds(
        seed_rows("query_rule_sets"), seed_rows("assay_groups"), actor="installer"
    )
    for row in rows:
        for rule in row["content"]["exceptions"]:
            old = {"id": rule["id"], "mode": rule["mode"], **legacy[rule["id"]]}
            old_clause = _exception_clause(resolved_query_policy("snv", None, [old]).exceptions[0])
            expected = {d["_id"] for d in collection.find(old_clause)}
            children = rule["condition"].get("children")
            for order in permutations(children) if children else [None]:
                changed = deepcopy(rule)
                if order:
                    changed["condition"]["children"] = list(order)
                clause = _exception_clause(
                    resolved_query_policy("snv", None, [changed]).exceptions[0]
                )
                assert {d["_id"] for d in collection.find(clause)} == expected


def test_escaped_installed_pattern_can_be_preserved_exactly():
    """An existing escaped literal must not silently become an insertion-length rule."""
    old = re.compile(r"\\w{10,200}", re.IGNORECASE)
    new = re.compile(r"\\[wW]{10,200}")
    for allele in ["A" * 20, "w" * 20, "\\" + "w" * 20, "\\" + "W" * 20, "\\w"]:
        assert bool(old.search(allele)) == bool(new.search(allele))


def test_installation_preserves_existing_and_retired_scopes(monkeypatch):
    db = mongomock.MongoClient().synthetic
    db.assay_groups.insert_many(seed_rows("assay_groups"))
    monkeypatch.setattr(install_query_rules, "run_transaction", lambda client, write: write(None))
    receipts = []
    monkeypatch.setattr(
        install_query_rules, "enqueue_audit", lambda *args, **kwargs: receipts.append(kwargs)
    )
    plan = install_query_rules.install(db, actor="installer")
    assert plan["missing_scopes"] == 8
    assert not db.query_rule_sets.count_documents({})
    install_query_rules.install(db, actor="installer", apply=True)
    db.query_rule_sets.update_one(
        {}, {"$set": {"status": "retired", "reason": "Withdrawn by center"}}
    )
    before = list(db.query_rule_sets.find())
    result = install_query_rules.install(db, actor="another", apply=True)
    assert result["missing_scopes"] == 0
    assert list(db.query_rule_sets.find()) == before
    assert len(receipts) == 1


def test_seed_rejects_unregistered_groups_and_duplicate_scopes():
    catalog = seed_rows("query_rule_sets")
    with pytest.raises(ValueError, match="registered group"):
        prepare_query_rule_seeds(catalog, [], actor="installer")
    with pytest.raises(ValueError, match="duplicate scopes"):
        prepare_query_rule_seeds(catalog + catalog, seed_rows("assay_groups"), actor="installer")


def test_query_roles_separate_lifecycle_grants():
    path = ROOT / "api/config/bootstrap/rbac/roles.seed.ndjson"
    roles = {
        row["name"]: row
        for line in path.read_text().splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    for role, additional in {
        "viewer": set(),
        "author": {"query_rules:draft"},
        "reviewer": {"query_rules:review"},
        "publisher": {"query_rules:publish", "query_rules:retire"},
    }.items():
        assert set(roles[f"query_rule_{role}"]["permissions"]) == {"query_rules:view"} | additional


def test_installation_file_overrides_same_id_without_losing_other_catalog_rules(tmp_path):
    """A center may replace one installed predicate without silently deleting its siblings."""
    policy = tmp_path / "policy.toml"
    policy.write_text("""[snv]
[cnv]
[translocation]
[fusion]
[pgx]
[[snv.exceptions]]
id = "flt3_svtype"
mode = "extend_consequence"
intents = ["somatic"]
assay_groups = ["hematology"]
genes = ["FLT3"]
info_fields_present = ["CENTER_SV"]
""")
    rows = prepare_query_rule_seeds(
        seed_rows("query_rule_sets"),
        seed_rows("assay_groups"),
        actor="installer",
        policy_path=policy,
    )
    row = next(row for row in rows if row["scope_key"] == "hematology__all__base__somatic_snvs")
    exceptions = {e["id"]: e for e in row["content"]["exceptions"]}
    assert len(exceptions) == 2
    assert exceptions["flt3_svtype"]["info_fields_present"] == ["CENTER_SV"]
    policy.write_text(policy.read_text() + 'asp_ids = ["unregistered_assay"]\n')
    with pytest.raises(ValueError, match="editor after assay activation"):
        prepare_query_rule_seeds(
            seed_rows("query_rule_sets"),
            seed_rows("assay_groups"),
            actor="installer",
            policy_path=policy,
        )
