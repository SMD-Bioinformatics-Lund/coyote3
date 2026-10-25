"""Individual metadata values and boundaries for service integrations."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from coyote3.application.resources.fields import ResourceFieldService
from coyote3.domain.exceptions import AppError


@pytest.fixture
def service():
    """Bind synthetic resource records to repository mocks."""
    return ResourceFieldService(
        panels=SimpleNamespace(
            get_asp=Mock(
                return_value={
                    "asp_id": "demo-panel",
                    "asp_group": "hematology",
                    "supported_analyses": ["SNV", "CNV"],
                }
            )
        ),
        configurations=SimpleNamespace(
            get_aspc_with_id=Mock(
                return_value={
                    "environment": "testing",
                    "reporting": {"report_sections": ["SNV"]},
                }
            )
        ),
        groups=SimpleNamespace(get=Mock(return_value={"parent_group_id": "hematology"})),
        diagnoses=SimpleNamespace(
            list_definitions=Mock(return_value=[{"diagnosis_id": "mpn", "display_name": "MPN"}]),
            assays_by_diagnosis=Mock(return_value={"mpn": ["demo-wgs", "demo-panel"]}),
        ),
        gene_lists=SimpleNamespace(
            get_isgl=Mock(
                return_value={
                    "genes": ["CALR", "JAK2"],
                    "list_type": ["snv"],
                    "is_public": False,
                }
            )
        ),
    )


def test_sample_fields_return_only_the_requested_value(service):
    """Sample fields return native values without exposing the sample document."""
    sample = {
        "name": "DEMO_001",
        "asp_id": "demo-panel",
        "environment": "testing",
        "reported": False,
        "version": 3,
        "filters": {"private": True},
    }
    assert service.sample_field(sample, "name") == "DEMO_001"
    assert service.sample_field(sample, "asp_id") == "demo-panel"
    assert service.sample_field(sample, "environment") == "testing"
    assert service.sample_field(sample, "reported") is False
    assert service.sample_field(sample, "version") == 3
    assert service.sample_field(sample, "time_added") is None
    service.panels.get_asp.assert_not_called()
    assert service.sample_field(sample, "asp_group") == "hematology"


@pytest.mark.parametrize("field", ["filters", "case", "files", "__dict__", "reporting.text"])
def test_sample_field_allowlist_rejects_arbitrary_document_access(service, field):
    """Unknown and nested clinical keys cannot be read as resource metadata."""
    with pytest.raises(AppError) as error:
        service.sample_field({"name": "DEMO_001"}, field)
    assert error.value.status_code == 422


def test_resource_fields_return_scalars_lists_counts_and_null(service):
    """Each resource provides a single typed value, including computed metadata."""
    assert service.assay_field("demo-panel", "supported_analyses") == ["SNV", "CNV"]
    assert service.configuration_field("demo-panel::mpn::testing", "environment") == "testing"
    assert service.configuration_field("demo-panel::mpn::testing", "report_sections") == ["SNV"]
    assert service.group_field("myeloid", "parent_group_id") == "hematology"
    assert service.diagnosis_field("mpn", "display_name") == "MPN"
    service.diagnoses.assays_by_diagnosis.assert_not_called()
    assert service.diagnosis_field("mpn", "asp_ids") == ["demo-panel", "demo-wgs"]
    assert service.gene_list_field("demo-mpn", "gene_count") == 2
    assert service.gene_list_field("demo-mpn", "list_type") == ["snv"]
    assert service.gene_list_field("demo-mpn", "is_public") is False
    assert service.gene_list_field("demo-mpn", "version") is None


@pytest.mark.parametrize(
    "method,key,field",
    [
        ("assay_field", "unknown", "asp_id"),
        ("configuration_field", "unknown", "environment"),
        ("group_field", "unknown", "display_name"),
        ("diagnosis_field", "unknown", "display_name"),
        ("gene_list_field", "unknown", "name"),
    ],
)
def test_missing_resource_returns_not_found(service, method, key, field):
    """Missing records return 404 rather than an ambiguous null field value."""
    service.panels.get_asp.return_value = None
    service.configurations.get_aspc_with_id.return_value = None
    service.groups.get.return_value = None
    service.gene_lists.get_isgl.return_value = None
    with pytest.raises(AppError) as error:
        getattr(service, method)(key, field)
    assert error.value.status_code == 404


def test_metadata_snapshots_project_only_allowed_values_and_reuse_existing_rules(service):
    sample = {
        "name": "DEMO_001",
        "asp_id": "demo-panel",
        "filters": {"synthetic": True},
        "files": {"private": "excluded"},
    }
    data = service.sample_metadata(sample)
    assert data.name == "DEMO_001"
    assert data.asp_group == "hematology"
    assert data.reported is None
    assert "files" not in data.model_dump()
    assert "filters" not in data.model_dump()
    service.panels.get_asp.reset_mock()
    assert service.assay_metadata("demo-panel").supported_analyses == ["SNV", "CNV"]
    service.panels.get_asp.assert_called_once_with("demo-panel")
    assert service.configuration_metadata("demo::base::testing").report_sections == ["SNV"]
    service.configurations.get_aspc_with_id.assert_called_once_with("demo::base::testing")
    assert service.group_metadata("demo").parent_group_id == "hematology"
    service.groups.get.assert_called_once_with("demo")
    assert service.diagnosis_metadata("mpn").asp_ids == ["demo-panel", "demo-wgs"]
    service.diagnoses.list_definitions.assert_called_once()
    assert service.gene_list_metadata("demo").gene_count == 2
    service.gene_lists.get_isgl.assert_called_once_with("demo", is_active=None)


@pytest.mark.parametrize(
    "method",
    [
        "assay_metadata",
        "configuration_metadata",
        "group_metadata",
        "diagnosis_metadata",
        "gene_list_metadata",
    ],
)
def test_metadata_missing_resources_return_not_found(service, method):
    service.panels.get_asp.return_value = None
    service.configurations.get_aspc_with_id.return_value = None
    service.groups.get.return_value = None
    service.diagnoses.list_definitions.return_value = []
    service.gene_lists.get_isgl.return_value = None
    with pytest.raises(AppError) as error:
        getattr(service, method)("unknown")
    assert error.value.status_code == 404
