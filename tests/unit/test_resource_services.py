from __future__ import annotations

from api.services.resource_annotation_service import ResourceAnnotationService
from api.services.resource_classification_service import ResourceClassificationService


class _AnnotationHandlerStub:
    def __init__(self) -> None:
        self.global_comments: list[dict] = []
        self.inserted_bulk: list[dict] | None = None
        self.deleted: list[dict] = []

    def add_anno_comment(self, comment: dict) -> None:
        self.global_comments.append(comment)

    def insert_annotation_bulk(self, docs: list[dict]) -> None:
        self.inserted_bulk = docs

    def delete_classified_variant(self, **kwargs) -> None:
        self.deleted.append(kwargs)


class _FusionHandlerStub:
    def __init__(self) -> None:
        self.comments: list[tuple[str, dict]] = []

    def add_fusion_comment(self, fusion_id: str, comment: dict) -> None:
        self.comments.append((fusion_id, comment))

    def get_fusion(self, fusion_id: str) -> dict:
        return {
            "_id": fusion_id,
            "SAMPLE_ID": "S1",
            "gene1": "EML4",
            "gene2": "ALK",
            "calls": [{"selected": 1, "breakpoint1": "2:100", "breakpoint2": "2:200"}],
        }

    def get_selected_fusioncall(self, fusion: dict) -> dict:
        return fusion["calls"][0]


class _CnvHandlerStub:
    def __init__(self) -> None:
        self.comments: list[tuple[str, dict]] = []

    def add_cnv_comment(self, cnv_id: str, comment: dict) -> None:
        self.comments.append((cnv_id, comment))

    def get_cnv(self, cnv_id: str) -> dict:
        return {
            "_id": cnv_id,
            "SAMPLE_ID": "S1",
            "chr": "7",
            "start": 10,
            "end": 20,
            "genes": [{"gene": "EGFR"}],
        }


class _TranslocHandlerStub:
    def __init__(self) -> None:
        self.comments: list[tuple[str, dict]] = []

    def add_transloc_comment(self, transloc_id: str, comment: dict) -> None:
        self.comments.append((transloc_id, comment))

    def get_transloc(self, transloc_id: str) -> dict:
        return {
            "_id": transloc_id,
            "SAMPLE_ID": "S1",
            "CHROM": "1",
            "POS": 100,
            "ALT": "2:200",
            "INFO": {"ANN": [{"Gene_Name": "BCR&ABL1"}]},
        }


class _VariantHandlerStub:
    def add_var_comment(self, variant_id: str, comment: dict) -> None:
        self.variant_comment = (variant_id, comment)


class _RepoStub:
    def __init__(self) -> None:
        self.annotation_handler = _AnnotationHandlerStub()
        self.fusion_handler = _FusionHandlerStub()
        self.cnv_handler = _CnvHandlerStub()
        self.transloc_handler = _TranslocHandlerStub()
        self.variant_handler = _VariantHandlerStub()
        self.oncokb_handler = type("_OncoKB", (), {"get_oncokb_gene": staticmethod(lambda gene: None)})()


def _nomenclature(form_data: dict) -> tuple[str, str]:
    if form_data.get("fusionpoints"):
        return "f", form_data["fusionpoints"]
    if form_data.get("translocpoints"):
        return "t", form_data["translocpoints"]
    if form_data.get("cnvvar"):
        return "cn", form_data["cnvvar"]
    return "p", form_data["var_p"]


def _comment_doc(form_data: dict, *, nomenclature: str, variant: str) -> dict:
    return {"text": form_data["text"], "nomenclature": nomenclature, "variant": variant}


def _classification_doc(*, variant: str, nomenclature: str, class_num: int, variant_data: dict, **kwargs) -> dict:
    return {
        "variant": variant,
        "nomenclature": nomenclature,
        "class": class_num,
        "variant_data": variant_data,
        "text": kwargs.get("text"),
        "source": kwargs.get("source"),
    }


def test_resource_annotation_service_routes_cnv_comment_to_cnv_handler():
    repo = _RepoStub()
    service = ResourceAnnotationService(repository=repo)

    resource = service.create_annotation(
        form_data={"text": "note", "cnvvar": "7:10-20"},
        target_id="cnv-1",
        get_variant_nomenclature_fn=_nomenclature,
        create_comment_doc_fn=_comment_doc,
    )

    assert resource == "cnv_comment"
    assert repo.cnv_handler.comments == [("cnv-1", {"text": "note", "nomenclature": "cn", "variant": "7:10-20"})]


def test_resource_annotation_service_routes_translocation_comment_to_translocation_handler():
    repo = _RepoStub()
    service = ResourceAnnotationService(repository=repo)

    resource = service.create_annotation(
        form_data={"text": "note", "translocpoints": "1:100^2:200"},
        target_id="tl-1",
        get_variant_nomenclature_fn=_nomenclature,
        create_comment_doc_fn=_comment_doc,
    )

    assert resource == "translocation_comment"
    assert repo.transloc_handler.comments[0][0] == "tl-1"


def test_resource_classification_service_supports_fusion_bulk_tiering():
    repo = _RepoStub()
    service = ResourceClassificationService(repository=repo)

    service.set_tier_bulk(
        sample={"_id": "S1"},
        resource_type="fusion",
        resource_ids=["fus-1"],
        assay_group="rna",
        subpanel=None,
        apply=True,
        class_num=2,
        create_annotation_text_fn=lambda gene, consequence, assay_group, gene_oncokb=None: f"{gene}:{assay_group}",
        create_classified_variant_doc_fn=_classification_doc,
    )

    docs = repo.annotation_handler.inserted_bulk
    assert docs is not None
    assert len(docs) == 2
    assert docs[0]["nomenclature"] == "f"
    assert docs[0]["variant"] == "2:100^2:200"
    assert docs[0]["variant_data"]["gene1"] == "EML4"
    assert docs[0]["variant_data"]["gene2"] == "ALK"


def test_resource_classification_service_supports_translocation_bulk_removal():
    repo = _RepoStub()
    service = ResourceClassificationService(repository=repo)

    service.set_tier_bulk(
        sample={"_id": "S1"},
        resource_type="translocation",
        resource_ids=["tl-1"],
        assay_group="dna",
        subpanel="solid",
        apply=False,
        class_num=3,
        create_annotation_text_fn=lambda gene, consequence, assay_group, gene_oncokb=None: f"{gene}:{assay_group}",
        create_classified_variant_doc_fn=_classification_doc,
    )

    assert len(repo.annotation_handler.deleted) == 1
    assert repo.annotation_handler.deleted[0]["nomenclature"] == "t"
    assert repo.annotation_handler.deleted[0]["variant"] == "1:100^2:200"
