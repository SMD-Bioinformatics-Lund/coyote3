"""Raw RNA examples must validate through the actual parser and write contracts."""

from pathlib import Path

from api.application.ingest.analysis_parsers import RnaIngestParser
from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    normalize_collection_document,
)


def test_raw_rna_example_roots_match_single_document_write_contracts():
    root = Path("demo_data/ingest")
    parsed = RnaIngestParser.parse(
        {
            "expression_path": str(root / "generic_rna_expression.json"),
            "classification_path": str(root / "generic_rna_classification.json"),
            "qc": str(root / "generic_rna_qc.json"),
        }
    )
    assert set(parsed) == {"rna_expr", "rna_class", "rna_qc"}
    for key, document in parsed.items():
        assert isinstance(document, dict)
        normalized = normalize_collection_document(
            INGEST_DEPENDENT_COLLECTIONS[key], {**document, "SAMPLE_ID": "synthetic_parent"}
        )
        assert normalized["SAMPLE_ID"] == "synthetic_parent"
