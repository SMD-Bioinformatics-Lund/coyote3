"""Tests for sanitized knowledgebase release metadata."""

from types import SimpleNamespace

import mongomock
from coyote_mongo.knowledgebase.versions import KnowledgebaseVersionRepository
from mongo_test_support.settings import mongo_runtime


def test_lists_active_releases_without_source_file_metadata() -> None:
    database = mongomock.MongoClient().knowledgebase
    repository = KnowledgebaseVersionRepository(
        SimpleNamespace(app=mongo_runtime(), knowledgebase_versions_collection=database.versions)
    )
    database.versions.insert_many(
        [
            {
                "source": "cosmic_actionability",
                "release": "v21",
                "status": "active",
                "files": [{"path": "/private/source.tsv", "sha256": "secret"}],
                "collections": [
                    {"name": "cosmic_actionability", "documents": 12, "indexes": ["genes"]}
                ],
            },
            {"source": "civic", "release": "old", "status": "retired"},
        ]
    )

    assert repository.list_active_releases() == [
        {
            "source": "cosmic_actionability",
            "release": "v21",
            "status": "active",
            "published_at": None,
            "records": 12,
            "collections": [{"name": "cosmic_actionability", "records": 12}],
        }
    ]
