"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace

import coyote.application.dna.structural_variants as service_module
from coyote.application.dna.structural_variants import DnaStructuralService
from coyote_mongo.selection import compile_selection


def test_service_factory_and_config_resolution_use_injected_repositories(monkeypatch):
    store = SimpleNamespace(
        annotation_repository=object(),
        query_rule_repository=SimpleNamespace(describe_selection=compile_selection),
        assay_group_repository=object(),
        assay_diagnosis_repository=object(),
        copy_number_variant_repository=object(),
        translocation_repository=object(),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
        gene_list_repository=object(),
        bam_record_repository=object(),
        vep_metadata_repository=object(),
        cosmic_repository=object(),
    )
    service = DnaStructuralService.from_store(store)
    captured: dict[str, object] = {}

    def _resolve(sample, **repositories):
        captured["sample"] = sample
        captured.update(repositories)
        return {"resolved": True}

    monkeypatch.setattr(service_module, "get_formatted_assay_config", _resolve)

    assert service._get_formatted_assay_config({"_id": "S1"}) == {"resolved": True}
    assert captured["assay_panel_repository"] is store.assay_panel_repository
    assert captured["assay_configuration_repository"] is store.assay_configuration_repository
