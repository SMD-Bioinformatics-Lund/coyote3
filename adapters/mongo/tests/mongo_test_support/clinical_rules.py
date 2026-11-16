"""Package-local synthetic records and fake ports for independent tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from coyote.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote.application.reporting.clinical_rules.validation import content_hash
from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc


def _context():
    return prepare_report_context(
        sample={
            "name": "SYNTHETIC_1",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "environment": "testing",
        },
        asp={"asp_id": "assay_1", "asp_group": "demo", "accredited": True},
        aspc={
            "aspc_id": "assay_1_base_testing",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "environment": "testing",
            "reporting": {
                "report_sections": ["SNV", "CNV"],
                "language": "sv",
            },
        },
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "snvs": [
                {
                    "INFO": {
                        "selected_CSQ": {
                            "SYMBOL": "TP53",
                            "EXON": "7/11",
                            "HGVSp": "p.Arg248Gln",
                        }
                    },
                    "GT": [{"type": "case", "AF": 0.22}],
                    "classification": {"class": 1},
                }
            ]
        },
    )


def _document(*, status: str = "draft", active: bool = False) -> ClinicalRuleSetDoc:
    now = datetime.now(timezone.utc)
    published = status == "published"
    document = ClinicalRuleSetDoc.model_validate(
        {
            "_id": uuid4().hex[:24],
            "rule_set_id": "assay_1__base__sv",
            "content_version": 1,
            "revision": 1,
            "scope": {
                "asp_id": "assay_1",
                "diagnosis_id": "base",
                "analyte": "dna",
                "language": "sv",
            },
            "name": "Synthetic clinical rules",
            "status": status,
            "active": active,
            "analysis_declarations": {
                "SNV": {"narrative": "enabled"},
                "CNV": {"narrative": "none"},
            },
            "blocks": [
                {
                    "block_id": "finding_context",
                    "name": "Finding context",
                    "analysis": "SNV",
                    "evaluation": {"mode": "each_finding"},
                    "section": "Findings",
                    "section_order": 100,
                    "block_order": 10,
                    "show_heading": True,
                    "match_strategy": "first_match",
                    "rules": [
                        {
                            "rule_id": "tp53_exon",
                            "name": "TP53 exon finding",
                            "order": 10,
                            "condition": {
                                "type": "all",
                                "children": [
                                    {
                                        "type": "predicate",
                                        "fact": "finding.gene",
                                        "operator": "eq",
                                        "value": "TP53",
                                    },
                                    {
                                        "type": "any",
                                        "children": [
                                            {
                                                "type": "predicate",
                                                "fact": "finding.exon",
                                                "operator": "overlaps",
                                                "value": ["7", "8"],
                                            },
                                            {
                                                "type": "predicate",
                                                "fact": "finding.hgvsp",
                                                "operator": "eq",
                                                "value": "p.Arg273His",
                                            },
                                        ],
                                    },
                                ],
                            },
                            "output": [
                                {"type": "text", "value": "Finding in "},
                                {
                                    "type": "fact",
                                    "path": "finding.gene",
                                    "formatter": "gene_symbol",
                                },
                                {"type": "text", "value": "."},
                            ],
                        }
                    ],
                },
                {
                    "block_id": "result_state",
                    "name": "Result state",
                    "analysis": "SNV",
                    "evaluation": {"mode": "once"},
                    "section": "Summary",
                    "section_order": 200,
                    "block_order": 10,
                    "show_heading": False,
                    "match_strategy": "exactly_one",
                    "rules": [
                        {
                            "rule_id": "positive",
                            "name": "Positive result",
                            "order": 10,
                            "condition": {
                                "type": "collection_match",
                                "collection": "findings",
                                "quantifier": "any",
                                "where": {
                                    "type": "predicate",
                                    "fact": "item.tier",
                                    "operator": "in",
                                    "value": [1, 2, 3],
                                },
                            },
                            "output": [{"type": "text", "value": "Positive."}],
                        },
                        {
                            "rule_id": "negative",
                            "name": "Negative result",
                            "order": 20,
                            "condition": {
                                "type": "collection_match",
                                "collection": "findings",
                                "quantifier": "none",
                                "where": {
                                    "type": "predicate",
                                    "fact": "item.tier",
                                    "operator": "in",
                                    "value": [1, 2, 3],
                                },
                            },
                            "output": [{"type": "text", "value": "Negative."}],
                        },
                    ],
                },
            ],
            "test_cases": [
                {
                    "test_id": "tp53_positive",
                    "name": "Synthetic TP53 finding",
                    "facts": _context().model_dump(mode="json"),
                    "expected_rule_ids": ["tp53_exon", "positive"],
                    "expected_sections": {
                        "Findings": ["Finding in TP53."],
                        "Summary": ["Positive."],
                    },
                }
            ],
            "created_at": now,
            "created_by": "author",
            "updated_at": now,
            "updated_by": "author",
            "published_at": now if published else None,
            "published_by": "publisher" if published else None,
            "effective_from": now if published else None,
        }
    )
    document.content_hash = content_hash(document)
    return document
