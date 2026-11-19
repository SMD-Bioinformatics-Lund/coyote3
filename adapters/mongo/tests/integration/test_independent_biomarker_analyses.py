"""Independent measurement selection, ingestion, rules, snapshots, and migration."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.ingest.dependent_writes import replace_dependents
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.measurements import MEASUREMENTS
from mongo_test_support.settings import audit_context, mongo_runtime
from mongo_test_support.writes import repository_writes  # noqa: F401

pytestmark = pytest.mark.usefixtures("repository_writes")


def test_update_preserves_other_analyses_and_replaces_both_msi_methods():
    """Updating MSI drops its absent paired method but preserves HRD/TMB."""
    existing = {**deepcopy(MEASUREMENTS), "_id": "row", "SAMPLE_ID": "sample"}
    collection = SimpleNamespace(find=Mock(return_value=[existing]), delete_many=Mock())
    writer = Mock(return_value={"biomarkers": 1})
    service = SimpleNamespace(
        app=mongo_runtime(),
        _collection=lambda name: collection,
        _write_dependents=writer,
        collection_gateway=IngestCollectionGateway(
            context=audit_context(), collections={"biomarkers": collection}
        ),
    )
    preload = {"biomarkers": {"name": "SYNTHETIC-T", "MSIS": {"tot": 10, "som": 1, "per": 10}}}
    replace_dependents(
        service,
        preload=preload,
        sample_id="sample",
        sample_name="SYNTHETIC-T",
        session="transaction",
    )
    merged = writer.call_args.kwargs["preload"]["biomarkers"]
    assert "MSIP" not in merged
    assert merged["HRD"] == MEASUREMENTS["HRD"]
    assert merged["TMB"] == MEASUREMENTS["TMB"]
    assert writer.call_args.kwargs["session"] == "transaction"
    collection.find.assert_called_once_with({"SAMPLE_ID": "sample"}, session="transaction")
    assert existing["MSIP"] == MEASUREMENTS["MSIP"]


@pytest.mark.parametrize(
    "existing",
    [
        [{**MEASUREMENTS, "name": "different-source"}],
        [MEASUREMENTS, MEASUREMENTS],
    ],
)
def test_ambiguous_source_is_rejected_before_replacing_measurements(existing):
    collection = SimpleNamespace(find=Mock(return_value=existing), delete_many=Mock())
    service = SimpleNamespace(
        app=mongo_runtime(),
        _collection=lambda name: collection,
        _write_dependents=Mock(),
        collection_gateway=IngestCollectionGateway(
            context=audit_context(), collections={"biomarkers": collection}
        ),
    )
    with pytest.raises(ValueError):
        replace_dependents(
            service,
            preload={"biomarkers": MEASUREMENTS},
            sample_id="sample",
            sample_name="synthetic",
            session="transaction",
        )
    collection.delete_many.assert_not_called()
    service._write_dependents.assert_not_called()
