"""Paired scopes never grant an environment belonging to another assay."""

import mongomock
from coyote_mongo.assay_access import restrict_assay_access
from coyote_mongo.repositories.samples import SampleRepository

GRANTS = [
    {"asp_id": "assay_a", "environments": ["production", "development", "validation"]},
    {"asp_id": "assay_b", "environments": ["production"]},
]


def test_direct_sample_queries_rows_and_totals_preserve_pairs_and_search_intersection():
    collection = mongomock.MongoClient().test.samples
    collection.insert_many(
        [
            {
                "name": f"{assay}-{env}",
                "asp_id": assay,
                "environment": env,
                "ingest_status": "ready",
            }
            for assay in ("assay_a", "assay_b")
            for env in ("production", "development", "validation")
        ]
    )
    query = SampleRepository._build_samples_query(
        user_assays=["assay_a", "assay_b"],
        user_envs=["production", "development", "validation"],
        report=False,
        search_str="",
        assay_access=GRANTS,
    )
    assert collection.count_documents(query) == 4
    assert not collection.find_one({"$and": [query, {"name": "assay_b-development"}]})
    assert (
        collection.count_documents(restrict_assay_access({"environment": "development"}, GRANTS))
        == 1
    )
    assert collection.count_documents(restrict_assay_access({}, [])) == 0
