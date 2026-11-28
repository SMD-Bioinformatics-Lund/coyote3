"""Mongo collection boundary tests for internal ingest."""

from types import SimpleNamespace

from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.settings import mongo_runtime


class _Repository:
    def __init__(self, collection):
        self._collection = collection

    def get_collection(self):
        return self._collection


class _TrackingDatabase:
    def __init__(self):
        self.requested: list[str] = []

    def __getitem__(self, name: str):
        self.requested.append(name)
        return f"primary:{name}"


def test_from_store_uses_repository_database_bindings() -> None:
    """Ingest resolves knowledgebase and identity collections through repositories."""
    primary = _TrackingDatabase()
    repository_names = (
        "sample_repository",
        "variant_repository",
        "anno_vep_repository",
        "copy_number_variant_repository",
        "biomarker_repository",
        "pgx_repository",
        "translocation_repository",
        "d4_coverage_repository",
        "coverage_repository",
        "fusion_repository",
        "rna_expression_repository",
        "rna_classification_repository",
        "rna_quality_repository",
        "user_repository",
        "roles_repository",
        "permissions_repository",
        "reported_variant_repository",
        "assay_configuration_repository",
        "assay_panel_repository",
        "assay_group_repository",
        "gene_list_repository",
        "blacklist_repository",
        "brca_repository",
        "civic_repository",
        "cosmic_repository",
        "d4_coverage_blacklist_repository",
        "hgnc_repository",
        "expression_repository",
        "iarc_tp53_repository",
        "vep_metadata_repository",
    )
    store = SimpleNamespace(
        app=mongo_runtime(),
        coyote_db=primary,
        assay_diagnosis_repository=SimpleNamespace(
            definitions="clinical:diagnoses", get_collection=lambda: "clinical:associations"
        ),
        **{name: _Repository(name) for name in repository_names},
        civic_gene_collection="knowledgebase:civic_genes",
        oncokb_actionable_collection="knowledgebase:oncokb_actionable",
        oncokb_genes_collection="knowledgebase:oncokb_genes",
        oncokb_public_cache_repository=SimpleNamespace(
            app=mongo_runtime(),
            get_collection=lambda: "knowledgebase:oncokb_public",
            gene_collection="knowledgebase:oncokb_genes_public",
            cancer_gene_collection="knowledgebase:oncokb_cancer_genes_public",
        ),
        clinpgx_public_repository=_Repository("knowledgebase:clinpgx_genes_public"),
    )

    gateway = IngestCollectionGateway.from_store(store)

    assert gateway.collection("coverage") == "coverage_repository"
    assert gateway.collection("diagnoses") == "clinical:diagnoses"
    assert gateway.collection("diagnosis_associations") == "clinical:associations"
    assert gateway.collection("brcaexchange") == "brca_repository"
    assert gateway.collection("civic_genes") == "knowledgebase:civic_genes"
    assert gateway.collection("oncokb_actionable") == "knowledgebase:oncokb_actionable"
    assert gateway.collection("oncokb_public") == "knowledgebase:oncokb_public"
    assert gateway.collection("users") == "user_repository"
    assert gateway.collection("roles") == "roles_repository"
    assert gateway.collection("permissions") == "permissions_repository"
    assert not {
        "brcaexchange",
        "civic_genes",
        "civic_variants",
        "cosmic",
        "hpaexpr",
        "oncokb_actionable",
        "oncokb_genes",
        "oncokb_public",
        "users",
        "roles",
        "permissions",
    }.intersection(primary.requested)
