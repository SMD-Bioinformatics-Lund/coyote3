"""Unit tests for canonical variant identity generation and hashing."""

from __future__ import annotations

import pytest

from coyote3.contracts.schemas.dna import VariantsDoc
from coyote3.domain.dna.variant_identity import (
    build_simple_id,
    build_simple_id_hash_from_simple_id,
    ensure_variant_identity_fields,
)


def test_identical_variant_inputs_produce_identical_hashes() -> None:
    s1 = build_simple_id("chr17", "7579472", "c", "t")
    s2 = build_simple_id("17", 7579472, "C", "T")

    assert s1 == "17_7579472_C_T"
    assert s1 == s2
    assert build_simple_id_hash_from_simple_id(s1) == build_simple_id_hash_from_simple_id(s2)


def test_different_variant_inputs_produce_different_hashes() -> None:
    h1 = build_simple_id_hash_from_simple_id(build_simple_id("17", 7579472, "C", "T"))
    h2 = build_simple_id_hash_from_simple_id(build_simple_id("17", 7579472, "C", "A"))

    assert h1 != h2


def test_large_alleles_generate_stable_hash() -> None:
    ref = "A" * 2000
    alt = "T" * 4000
    simple = build_simple_id("chr1", 12345, ref, alt)
    digest = build_simple_id_hash_from_simple_id(simple)

    assert simple.startswith("1_12345_")
    assert len(digest) == 32


def test_historical_document_can_be_backfilled_safely() -> None:
    historical = {"CHROM": " chr17 ", "POS": "7579472", "REF": " c ", "ALT": " t "}
    normalized = ensure_variant_identity_fields(historical)

    assert normalized["simple_id"] == "17_7579472_C_T"
    assert normalized["simple_id_hash"] == "862b46287a08e369aa99f8f3777f44b9"


@pytest.mark.parametrize("simple_id", ["17_7579472_C_T", " chr17_07579472_c_t "])
def test_variant_contract_uses_the_canonical_hash_for_normalized_and_raw_ids(simple_id):
    """Contract validation accepts the digest produced by every canonical generation path."""
    digest = build_simple_id_hash_from_simple_id(simple_id)
    assert digest == "862b46287a08e369aa99f8f3777f44b9"
    document = VariantsDoc(
        SAMPLE_ID="synthetic-sample",
        CHROM="17",
        POS=7579472,
        REF="C",
        ALT="T",
        ID=".",
        INFO={
            "selected_CSQ": {"Feature": "SYNTHETIC_TRANSCRIPT"},
            "selected_CSQ_criteria": "ncbi_mane_plus_clinical",
        },
        simple_id=simple_id,
        simple_id_hash=digest,
    )
    assert document.simple_id_hash == digest
