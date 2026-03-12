"""Route registration checks for DNA structural REST aliases."""

from __future__ import annotations

from api.main import app as api_app


def test_restful_dna_structural_mutation_routes_are_registered():
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting" in paths
    assert "/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive" in paths
    assert "/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy" in paths
    assert "/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden" in paths
    assert "/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/interesting" in paths
    assert "/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive" in paths
    assert "/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden" in paths
