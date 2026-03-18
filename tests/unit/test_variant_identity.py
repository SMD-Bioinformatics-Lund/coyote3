"""Unit tests for canonical variant identity generation and hashing."""

from __future__ import annotations

from api.core.dna.variant_identity import (
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


def test_legacy_document_can_be_backfilled_safely() -> None:
    legacy = {"CHROM": " chr17 ", "POS": "7579472", "REF": " c ", "ALT": " t "}
    normalized = ensure_variant_identity_fields(legacy)

    assert normalized["simple_id"] == "17_7579472_C_T"
    assert normalized["simple_id_hash"] == "862b46287a08e369aa99f8f3777f44b9"
