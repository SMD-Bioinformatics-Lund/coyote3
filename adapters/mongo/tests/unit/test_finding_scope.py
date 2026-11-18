# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Finding inventory uses persisted sample identities and exact environment grants."""

from types import SimpleNamespace

import mongomock
from bson import ObjectId
from coyote_mongo.assay_access import finding_scope_query


def test_scoped_inventory_uses_ids_even_when_a_sample_name_matches_another_id():
    database = mongomock.MongoClient().synthetic_scope
    allowed_id, denied_id = ObjectId(), ObjectId()
    database.samples.insert_many(
        [
            {"_id": allowed_id, "name": str(denied_id), "asp_id": "dna", "environment": "testing"},
            {
                "_id": denied_id,
                "name": "OTHER_SAMPLE",
                "asp_id": "dna",
                "environment": "validation",
            },
        ]
    )
    database.findings.insert_many(
        [
            {"_id": "allowed", "SAMPLE_ID": str(allowed_id)},
            {"_id": "denied", "SAMPLE_ID": str(denied_id)},
        ]
    )
    adapter = SimpleNamespace(samples_collection=database.samples)
    grants = [{"asp_id": "dna", "environments": ["testing"]}]

    rows = list(database.findings.find(finding_scope_query(adapter, grants)))
    assert [row["_id"] for row in rows] == ["allowed"]
    assert database.findings.count_documents(finding_scope_query(adapter, [])) == 0
    assert database.findings.count_documents(finding_scope_query(adapter, None)) == 2


def test_reported_finding_scope_still_uses_the_snapshot_sample_name():
    database = mongomock.MongoClient().synthetic_scope
    database.samples.insert_many(
        [
            {"name": "ALLOWED", "asp_id": "dna", "environment": "testing"},
            {"name": "DENIED", "asp_id": "rna", "environment": "testing"},
        ]
    )
    database.reported.insert_many([{"sample_name": "ALLOWED"}, {"sample_name": "DENIED"}])
    scope = finding_scope_query(
        SimpleNamespace(samples_collection=database.samples),
        [{"asp_id": "dna", "environments": ["testing"]}],
        "sample_name",
    )
    assert [row["sample_name"] for row in database.reported.find(scope)] == ["ALLOWED"]
