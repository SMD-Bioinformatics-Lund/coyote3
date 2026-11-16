"""Installed identities remain immutable even to authenticated superusers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.ingest.collection_writes import upsert_collection_document
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.settings import audit_context


@pytest.mark.parametrize("collection", ["users", "roles", "permissions"])
def test_ingest_cannot_replace_installed_identity(collection):
    repository = Mock()
    repository.find_one.return_value = {"system_managed": True}
    service = SimpleNamespace(
        collection_gateway=IngestCollectionGateway(
            context=audit_context(), collections={collection: repository}
        )
    )
    with pytest.raises(AppError):
        upsert_collection_document(
            service,
            collection=collection,
            match={"_id": "installed"},
            document={"system_managed": False},
        )
    repository.replace_one.assert_not_called()
