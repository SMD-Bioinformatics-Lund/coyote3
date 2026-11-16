"""Bundled application ASP configuration rejects cross-modality report ordering."""

import json
from pathlib import Path

import pytest
from coyote.contracts.schemas.assay import AspConfigDoc
from pydantic import ValidationError


@pytest.mark.parametrize("field", ["summary_text_order", "summary_table_order"])
def test_dna_order_cannot_introduce_an_rna_analysis(field):
    source = json.loads(
        Path("tests/fixtures/collections/all_collections_dummy/asp_configs.json").read_text()
    )[0]
    source["reporting"][field] = ["FUSION"]
    with pytest.raises(ValidationError, match="outside this modality"):
        AspConfigDoc.model_validate(source)
