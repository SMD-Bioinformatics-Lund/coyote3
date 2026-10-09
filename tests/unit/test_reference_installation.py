"""Verify optional bundled reference installation without live database access."""

import mongomock

from scripts.bootstrap import install_reference_data
from scripts.bootstrap.bootstrap_database import (
    DEFAULT_RBAC_DIR,
    DEFAULT_REFERENCE_DIR,
    _build_seed_documents,
)
from scripts.bootstrap.build_seed_bundle import load_reference_seed_pack


def test_application_seed_loading_does_not_read_reference_snapshots(tmp_path):
    """Malformed large reference files must not affect application-only bootstrap."""
    (tmp_path / "hgnc_genes.seed.ndjson").write_text("not json")
    (tmp_path / "vep_metadata.seed.ndjson").write_text("not json")
    (tmp_path / "assay_groups.seed.ndjson").write_text('{"group_id":"synthetic"}\n')
    assert load_reference_seed_pack(tmp_path, include_knowledgebase=False) == {
        "assay_groups": [{"group_id": "synthetic"}]
    }
    seed = _build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        demo_center_dir=None,
        actor="synthetic.admin",
        include_knowledgebase=False,
    )
    assert {"roles", "permissions", "assay_groups", "query_rule_sets"} <= seed.keys()
    assert not {"hgnc_genes", "vep_metadata", "vep_diagrams"} & seed.keys()


def test_reference_install_preserves_existing_data_and_does_not_create_indexes(monkeypatch):
    client = mongomock.MongoClient()
    db = client.knowledgebase
    db.hgnc_genes.insert_one({"hgnc_id": "existing"})
    before = list(db.hgnc_genes.find())
    monkeypatch.setattr(
        install_reference_data,
        "_build_seed_documents",
        lambda **kwargs: {
            "hgnc_genes": [{"hgnc_id": "synthetic"}],
            "vep_metadata": [{"id": "synthetic"}],
        },
    )
    monkeypatch.setattr(
        install_reference_data, "load_seed_diagrams", lambda *_: [{"id": "diagram"}]
    )
    for _ in range(2):
        install_reference_data.install_references(
            db, actor="synthetic.admin", reference_dir=DEFAULT_REFERENCE_DIR
        )
        assert list(db.hgnc_genes.find()) == before
        assert db.vep_metadata.count_documents({}) == 1
        for name in db.list_collection_names():
            assert set(db[name].index_information()) == {"_id_"}
    assert client.list_database_names() == ["knowledgebase"]
