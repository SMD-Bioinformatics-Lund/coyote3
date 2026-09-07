from api.config.application_modules import modules_for_api_path


def _keys(path: str) -> set[str]:
    return {module.key for module in modules_for_api_path(path)}


def test_sample_analysis_routes_map_to_their_analysis_modules():
    assert _keys("/api/v1/samples/CASE_001/small-variants") == {"dna_analysis"}
    assert _keys("/api/v1/samples/CASE_001/cnvs") == {"dna_analysis"}
    assert _keys("/api/v1/samples/CASE_001/fusions") == {"rna_analysis"}


def test_variant_knowledgebase_lookup_requires_both_modules():
    assert _keys("/api/v1/samples/CASE_001/small-variants/VAR_001/oncokb-public") == {
        "dna_analysis",
        "knowledgebases",
    }


def test_optional_workflow_routes_map_to_independent_modules():
    assert _keys("/api/v1/samples/CASE_001/reports/dna/preview") == {"reports"}
    assert _keys("/api/v1/common/search/tiered_variants") == {"variant_search"}
    assert _keys("/api/v1/internal/ingest/sample-bundle") == {"ingest_workspace"}
    assert _keys("/api/v1/public/assay-catalog/matrix") == {"assay_catalog"}


def test_core_recovery_and_oversight_routes_are_not_switchable():
    assert _keys("/api/v1/admin/controls") == set()
    assert _keys("/api/v1/admin/audit-events") == set()
    assert _keys("/api/v1/auth/sessions") == set()
    assert _keys("/api/v1/public/modules") == set()


def test_public_oncokb_refresh_requires_the_knowledgebase_module():
    assert _keys("/api/v1/admin/controls/knowledgebases/oncokb-public/refresh") == {
        "knowledgebases"
    }
