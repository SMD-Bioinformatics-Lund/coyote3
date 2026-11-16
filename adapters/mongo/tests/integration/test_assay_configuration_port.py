"""The Mongo implementation preserves the core assay-configuration port semantics."""

from inspect import signature
from types import SimpleNamespace

import mongomock
import pytest
from coyote.domain.repository_protocols import AssayConfigurationRepositoryProtocol
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository


@pytest.fixture
def repository() -> ASPConfigRepository:
    """Bind active and historical synthetic configurations to the real repository."""
    collection = mongomock.MongoClient().test.asp_configs
    collection.insert_many(
        [
            {
                "asp_id": "panel-a",
                "is_active": True,
                "analysis_types": ["SNV", "CNV"],
                "reporting": {"report_sections": ["SNV"]},
            },
            {
                "asp_id": "panel-a",
                "is_active": True,
                "analysis_types": ["CNV", "FUSION", "COVERAGE"],
                "reporting": {"report_sections": ["CNV", "FUSION"]},
            },
            {
                "asp_id": "panel-a",
                "is_active": False,
                "analysis_types": ["PGX"],
                "reporting": {"report_sections": ["PGX"]},
            },
            {
                "asp_id": "panel-b",
                "is_active": True,
                "analysis_types": ["PGX"],
                "reporting": {"report_sections": ["PGX"]},
            },
        ]
    )
    return ASPConfigRepository(SimpleNamespace(aspc_collection=collection))


def test_declared_default_and_adapter_default_count_the_same_configurations(repository):
    """A host using the published default must receive the same total as a direct call."""
    declared_default = (
        signature(AssayConfigurationRepositoryProtocol.count_aspcs).parameters["is_active"].default
    )
    assert repository.count_aspcs() == repository.count_aspcs(declared_default) == 4
    assert repository.count_aspcs(None) == 4
    assert repository.count_aspcs(True) == 3
    assert repository.count_aspcs(False) == 1


def test_analysis_rollup_scopes_active_configurations_and_counts_categories(repository):
    """Historical and unselected assays do not affect enabled or reportable totals."""
    port: AssayConfigurationRepositoryProtocol = repository
    assert port.get_dashboard_analysis_type_rollup(asp_ids=["panel-a"]) == [
        {"analysis_type": "CNV", "enabled": 2, "reportable": 1},
        {"analysis_type": "COVERAGE", "enabled": 1, "reportable": 0},
        {"analysis_type": "FUSION", "enabled": 1, "reportable": 1},
        {"analysis_type": "SNV", "enabled": 1, "reportable": 1},
    ]
    assert port.get_dashboard_analysis_type_rollup(asp_ids=["panel-b"]) == [
        {"analysis_type": "PGX", "enabled": 1, "reportable": 1}
    ]


def test_analysis_rollup_normalizes_assay_scope_without_counting_duplicates(repository):
    """Case, whitespace and duplicates do not multiply an assay's configuration counts."""
    assert repository.get_dashboard_analysis_type_rollup(
        asp_ids=["PANEL-A", " panel-a ", ""]
    ) == repository.get_dashboard_analysis_type_rollup(asp_ids=["panel-a"])
    assert repository.get_dashboard_analysis_type_rollup(asp_ids=[]) == []
    assert repository.get_dashboard_analysis_type_rollup(asp_ids=["missing-panel"]) == []
    with pytest.raises(ValueError):
        repository.get_dashboard_analysis_type_rollup(asp_ids=["invalid assay!"])
