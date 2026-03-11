from __future__ import annotations

from types import SimpleNamespace

from api.infra.repositories import dna_route_mongo, rna_route_mongo


def test_dna_route_repository_binds_expected_handlers(monkeypatch):
    fake_store = SimpleNamespace(
        cnv_handler=object(),
        asp_handler=object(),
        isgl_handler=object(),
        variant_handler=object(),
        blacklist_handler=object(),
        bam_service_handler=object(),
        vep_meta_handler=object(),
        sample_handler=object(),
        schema_handler=object(),
        oncokb_handler=object(),
        biomarker_handler=object(),
        transloc_handler=object(),
        annotation_handler=object(),
        expression_handler=object(),
        civic_handler=object(),
        brca_handler=object(),
        iarc_tp53_handler=object(),
        fusion_handler=object(),
    )
    monkeypatch.setattr(dna_route_mongo, "store", fake_store)
    repo = dna_route_mongo.MongoDNARouteRepository()

    assert repo.cnv_handler is fake_store.cnv_handler
    assert repo.variant_handler is fake_store.variant_handler
    assert repo.transloc_handler is fake_store.transloc_handler
    assert repo.annotation_handler is fake_store.annotation_handler
    assert repo.fusion_handler is fake_store.fusion_handler


def test_rna_route_repository_binds_expected_handlers(monkeypatch):
    fake_store = SimpleNamespace(
        schema_handler=object(),
        asp_handler=object(),
        isgl_handler=object(),
        sample_handler=object(),
        fusion_handler=object(),
    )
    monkeypatch.setattr(rna_route_mongo, "store", fake_store)
    repo = rna_route_mongo.MongoRNARouteRepository()

    assert repo.schema_handler is fake_store.schema_handler
    assert repo.isgl_handler is fake_store.isgl_handler
    assert repo.sample_handler is fake_store.sample_handler
    assert repo.fusion_handler is fake_store.fusion_handler
