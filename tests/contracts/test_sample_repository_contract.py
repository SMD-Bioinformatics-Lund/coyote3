"""Repository contract tests for sample mutation persistence adapters."""

from __future__ import annotations

from types import SimpleNamespace

from api.infra.repositories.samples_mongo import SampleRepository


def test_sample_repository_contract(monkeypatch):
    sample_calls = []
    blacklist_calls = []
    store_stub = SimpleNamespace(
        sample_handler=SimpleNamespace(
            add_sample_comment=lambda sample_id, doc: sample_calls.append(
                ("add_sample_comment", sample_id, doc)
            ),
            hide_sample_comment=lambda sample_id, comment_id: sample_calls.append(
                ("hide_sample_comment", sample_id, comment_id)
            ),
            unhide_sample_comment=lambda sample_id, comment_id: sample_calls.append(
                ("unhide_sample_comment", sample_id, comment_id)
            ),
            update_sample_filters=lambda sample_id, filters: sample_calls.append(
                ("update_sample_filters", sample_id, filters)
            ),
            reset_sample_settings=lambda sample_id, filters: sample_calls.append(
                ("reset_sample_settings", sample_id, filters)
            ),
        ),
        groupcov_handler=SimpleNamespace(
            blacklist_coord=lambda gene, coord, region, assay_group: blacklist_calls.append(
                ("blacklist_coord", gene, coord, region, assay_group)
            ),
            blacklist_gene=lambda gene, assay_group: blacklist_calls.append(
                ("blacklist_gene", gene, assay_group)
            ),
            remove_blacklist=lambda obj_id: blacklist_calls.append(("remove_blacklist", obj_id)),
        ),
    )
    monkeypatch.setattr("api.infra.repositories.samples_mongo.store", store_stub)

    repo = SampleRepository()

    repo.add_sample_comment("S1", {"text": "note"})
    repo.hide_sample_comment("S1", "C1")
    repo.unhide_sample_comment("S1", "C1")
    repo.update_sample_filters("S1", {"min_depth": 10})
    repo.reset_sample_settings("S1", {"max_freq": 0.1})
    repo.blacklist_coord("TP53", "chr17:1-10", "probe", "dna")
    repo.blacklist_gene("EGFR", "dna")
    repo.remove_blacklist("BL1")

    assert sample_calls == [
        ("add_sample_comment", "S1", {"text": "note"}),
        ("hide_sample_comment", "S1", "C1"),
        ("unhide_sample_comment", "S1", "C1"),
        ("update_sample_filters", "S1", {"min_depth": 10}),
        ("reset_sample_settings", "S1", {"max_freq": 0.1}),
    ]
    assert blacklist_calls == [
        ("blacklist_coord", "TP53", "chr17:1-10", "probe", "dna"),
        ("blacklist_gene", "EGFR", "dna"),
        ("remove_blacklist", "BL1"),
    ]
