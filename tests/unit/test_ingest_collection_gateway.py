"""Mongo collection boundary tests for internal ingest."""

from types import SimpleNamespace

from api.infra.mongo.ingest_gateway import IngestCollectionGateway


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
        "translocation_repository",
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
        "gene_list_repository",
        "blacklist_repository",
        "brca_repository",
        "civic_repository",
        "cosmic_repository",
        "grouped_coverage_repository",
        "hgnc_repository",
        "expression_repository",
        "iarc_tp53_repository",
        "vep_metadata_repository",
    )
    store = SimpleNamespace(
        coyote_db=primary,
        **{name: _Repository(name) for name in repository_names},
        civic_gene_collection="knowledgebase:civic_genes",
        oncokb_actionable_collection="knowledgebase:oncokb_actionable",
        oncokb_genes_collection="knowledgebase:oncokb_genes",
        oncokb_public_cache_repository=SimpleNamespace(
            get_collection=lambda: "knowledgebase:oncokb_public",
            gene_collection="knowledgebase:oncokb_genes_public",
            cancer_gene_collection="knowledgebase:oncokb_cancer_genes_public",
        ),
        clinpgx_public_repository=_Repository("knowledgebase:clinpgx_genes_public"),
    )

    gateway = IngestCollectionGateway.from_store(store)

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
