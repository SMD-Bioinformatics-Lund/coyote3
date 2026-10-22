"""Structural repository streams hydrate comments without materializing the cursor."""

from types import SimpleNamespace

import pytest

from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.translocations import TranslocsRepository


@pytest.mark.parametrize(
    "repository_type,method",
    [
        (CNVsRepository, "get_sample_cnvs"),
        (TranslocsRepository, "get_sample_translocations"),
    ],
)
def test_comment_hydration_consumes_only_one_batch_at_a_time(repository_type, method, monkeypatch):
    """The first row requires at most 100 inputs and remaining rows retain source order."""
    consumed = []
    hydrated = []

    def documents(query):
        """Yield synthetic documents without a collection-sized list."""
        assert query == {"SAMPLE_ID": "synthetic"}
        for index in range(245):
            consumed.append(index)
            yield {"_id": index, "SAMPLE_ID": "synthetic", "INFO": {}}

    def hydrate(rows):
        """Record batch sizes while emulating comment hydration."""
        hydrated.append(len(rows))
        return [{**row, "comments": []} for row in rows]

    repository = object.__new__(repository_type)
    monkeypatch.setattr(repository, "get_collection", lambda: SimpleNamespace(find=documents))
    monkeypatch.setattr(repository, "hydrate_finding_comments_many", hydrate)
    stream = getattr(repository, method)({"SAMPLE_ID": "synthetic"}, stream=True)
    assert not consumed
    first = next(stream)
    assert len(consumed) == 100
    assert first["_id"] == 0
    assert [first["_id"], *(row["_id"] for row in stream)] == list(range(245))
    assert hydrated == [100, 100, 45]
