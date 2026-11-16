"""Adapters own executable queries and provider IDs; core selections are plain values."""

from coyote.domain.finding_repositories import SampleFindingReader
from coyote.domain.selection import RecordField, Selection, select


def test_repository_port_can_use_records_without_mongo_translation():
    class MemoryFindings:
        """Implement a small synthetic subset of the sample-owned selection port."""

        def preview_sample_findings(self, sample_id, query, limit=10001):
            assert isinstance(query, Selection)
            assert set(query.criteria) <= {RecordField.SAMPLE, "gene"}
            records = [
                {"_id": "one", "sample": "authorized", "gene": "TP53"},
                {"_id": "two", "sample": "other", "gene": "TP53"},
            ]
            return [
                row
                for row in records
                if row["sample"] == sample_id
                and row["sample"] == query.criteria.get(RecordField.SAMPLE, sample_id)
                and row["gene"] == query.criteria.get("gene", row["gene"])
            ][:limit]

    reader: SampleFindingReader = MemoryFindings()
    assert [
        row["_id"] for row in reader.preview_sample_findings("authorized", select({"gene": "TP53"}))
    ] == ["one"]
    assert reader.preview_sample_findings("authorized", select({RecordField.SAMPLE: "other"})) == []
