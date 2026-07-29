from __future__ import annotations

from api.application.classification.tiering import ResourceClassificationService
from api.application.classification.variant_annotation import ResourceAnnotationService


class _AnnotationHandlerStub:
    """Provide  AnnotationHandlerStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.global_comments: list[dict] = []
        self.inserted_bulk: list[dict] | None = None
        self.deleted: list[dict] = []

    def add_anno_comment(self, comment: dict) -> None:
        """Add anno comment.

        Args:
            comment (dict): Value for ``comment``.

        Returns:
            None.
        """
        self.global_comments.append(comment)

    def insert_annotation_bulk(self, docs: list[dict]) -> None:
        """Insert annotation bulk.

        Args:
            docs (list[dict]): Value for ``docs``.

        Returns:
            None.
        """
        self.inserted_bulk = docs

    def delete_classified_variant(self, **kwargs) -> None:
        """Delete classified variant.

        Args:
            **kwargs: Additional keyword values for ``kwargs``.

        Returns:
            None.
        """
        self.deleted.append(kwargs)


class _FusionHandlerStub:
    """Provide  FusionHandlerStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.comments: list[tuple[str, dict]] = []

    def add_fusion_comment(self, fusion_id: str, comment: dict) -> None:
        """Add fusion comment.

        Args:
            fusion_id (str): Value for ``fusion_id``.
            comment (dict): Value for ``comment``.

        Returns:
            None.
        """
        self.comments.append((fusion_id, comment))

    def get_fusion(self, fusion_id: str) -> dict:
        """Return fusion.

        Args:
            fusion_id (str): Value for ``fusion_id``.

        Returns:
            dict: The function result.
        """
        return {
            "_id": fusion_id,
            "SAMPLE_ID": "S1",
            "gene1": "EML4",
            "gene2": "ALK",
            "calls": [{"selected": 1, "breakpoint1": "2:100", "breakpoint2": "2:200"}],
        }

    def get_selected_fusioncall(self, fusion: dict) -> dict:
        """Return selected fusioncall.

        Args:
            fusion (dict): Value for ``fusion``.

        Returns:
            dict: The function result.
        """
        return fusion["calls"][0]


class _CnvHandlerStub:
    """Provide  CnvHandlerStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.comments: list[tuple[str, dict]] = []

    def add_cnv_comment(self, cnv_id: str, comment: dict) -> None:
        """Add cnv comment.

        Args:
            cnv_id (str): Value for ``cnv_id``.
            comment (dict): Value for ``comment``.

        Returns:
            None.
        """
        self.comments.append((cnv_id, comment))

    def get_cnv(self, cnv_id: str) -> dict:
        """Return cnv.

        Args:
            cnv_id (str): Value for ``cnv_id``.

        Returns:
            dict: The function result.
        """
        return {
            "_id": cnv_id,
            "SAMPLE_ID": "S1",
            "chr": "7",
            "start": 10,
            "end": 20,
            "genes": [{"gene": "EGFR"}],
        }


class _TranslocHandlerStub:
    """Provide  TranslocHandlerStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.comments: list[tuple[str, dict]] = []

    def add_transloc_comment(self, transloc_id: str, comment: dict) -> None:
        """Add transloc comment.

        Args:
            transloc_id (str): Value for ``transloc_id``.
            comment (dict): Value for ``comment``.

        Returns:
            None.
        """
        self.comments.append((transloc_id, comment))

    def get_transloc(self, transloc_id: str) -> dict:
        """Return transloc.

        Args:
            transloc_id (str): Value for ``transloc_id``.

        Returns:
            dict: The function result.
        """
        return {
            "_id": transloc_id,
            "SAMPLE_ID": "S1",
            "CHROM": "1",
            "POS": 100,
            "ALT": "2:200",
            "INFO": {"ANN": [{"Gene_Name": "BCR&ABL1"}]},
        }


class _VariantHandlerStub:
    """Provide  VariantHandlerStub behavior."""

    def add_var_comment(self, variant_id: str, comment: dict) -> None:
        """Add var comment.

        Args:
            variant_id (str): Value for ``variant_id``.
            comment (dict): Value for ``comment``.

        Returns:
            None.
        """
        self.variant_comment = (variant_id, comment)

    def get_variant(self, variant_id: str) -> dict:
        """Return a small variant fixture for classification tests."""
        return {
            "_id": variant_id,
            "SAMPLE_ID": "S1",
            "CHROM": "17",
            "POS": 76736896,
            "REF": "T",
            "ALT": "C",
            "INFO": {
                "selected_CSQ": {
                    "Feature": "ENST00000359995",
                    "SYMBOL": "SRSF2",
                    "HGVSp": "p.Met89Val",
                    "HGVSc": "c.265A>G",
                    "Consequence": "missense_variant",
                }
            },
        }


class _RepoStub:
    """Provide  RepoStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.annotation_repository = _AnnotationHandlerStub()
        self.fusion_repository = _FusionHandlerStub()
        self.copy_number_variant_repository = _CnvHandlerStub()
        self.translocation_repository = _TranslocHandlerStub()
        self.variant_repository = _VariantHandlerStub()
        self.oncokb_repository = type(
            "_OncoKB", (), {"get_oncokb_gene": staticmethod(lambda gene: None)}
        )()
        self.assay_configuration_repository = type(
            "_Aspc",
            (),
            {
                "get_aspc_no_meta": staticmethod(
                    lambda assay, profile, subpanel: {
                        "_id": "aspc-oid",
                        "aspc_id": "assay:production:base",
                        "asp_id": "assay",
                        "asp_group": "dna",
                        "subpanel_id": subpanel or "base",
                        "environment": profile,
                        "version": 2,
                    }
                )
            },
        )()
        self.assay_panel_repository = type(
            "_Asp",
            (),
            {"get_asp": staticmethod(lambda asp_id: {"asp_id": asp_id, "asp_group": "dna"})},
        )()


def _nomenclature(form_data: dict) -> tuple[str, str]:
    """Nomenclature.

    Args:
            form_data: Form data.

    Returns:
            The  nomenclature result.
    """
    if form_data.get("fusionpoints"):
        return "f", form_data["fusionpoints"]
    if form_data.get("translocpoints"):
        return "t", form_data["translocpoints"]
    if form_data.get("cnvvar"):
        return "cn", form_data["cnvvar"]
    return "p", form_data["var_p"]


def _comment_doc(form_data: dict, *, nomenclature: str, variant: str) -> dict:
    """Comment doc.

    Args:
            form_data: Form data.
            nomenclature: Nomenclature. Keyword-only argument.
            variant: Variant. Keyword-only argument.

    Returns:
            The  comment doc result.
    """
    return {"text": form_data["text"], "nomenclature": nomenclature, "variant": variant}


def _classification_doc(
    *, variant: str, nomenclature: str, class_num: int, variant_data: dict, **kwargs
) -> dict:
    """Classification doc.

    Args:
            variant: Variant. Keyword-only argument.
            nomenclature: Nomenclature. Keyword-only argument.
            class_num: Class num. Keyword-only argument.
            variant_data: Variant data. Keyword-only argument.
            **kwargs: Kwargs. Additional keyword arguments.

    Returns:
            The  classification doc result.
    """
    assert "source" not in kwargs
    return {
        "variant": variant,
        "nomenclature": nomenclature,
        "class": class_num,
        "variant_data": variant_data,
        "text": kwargs.get("text"),
    }


def _classification_service(repo: _RepoStub) -> ResourceClassificationService:
    return ResourceClassificationService(
        annotation_repository=repo.annotation_repository,
        variant_repository=repo.variant_repository,
        oncokb_repository=repo.oncokb_repository,
        fusion_repository=repo.fusion_repository,
        copy_number_variant_repository=repo.copy_number_variant_repository,
        translocation_repository=repo.translocation_repository,
        assay_panel_repository=repo.assay_panel_repository,
        assay_configuration_repository=repo.assay_configuration_repository,
    )


def test_resource_annotation_service_routes_cnv_comment_to_copy_number_variant_repository(
    monkeypatch,
):
    """Test resource annotation service routes cnv comment to copy-number-variant handler.

    Returns:
        The function result.
    """
    _ = monkeypatch
    repo = _RepoStub()
    service = ResourceAnnotationService(
        annotation_repository=repo.annotation_repository,
        fusion_repository=repo.fusion_repository,
        translocation_repository=repo.translocation_repository,
        copy_number_variant_repository=repo.copy_number_variant_repository,
        variant_repository=repo.variant_repository,
    )

    resource = service.create_annotation(
        form_data={"text": "note", "cnvvar": "7:10-20"},
        target_id="cnv-1",
        get_variant_nomenclature_fn=_nomenclature,
        create_comment_doc_fn=_comment_doc,
    )

    assert resource == "cnv_comment"
    assert repo.copy_number_variant_repository.comments == [
        ("cnv-1", {"text": "note", "nomenclature": "cn", "variant": "7:10-20"})
    ]


def test_resource_annotation_service_routes_translocation_comment_to_translocation_repository(
    monkeypatch,
):
    """Test resource annotation service routes translocation comment to translocation handler.

    Returns:
        The function result.
    """
    _ = monkeypatch
    repo = _RepoStub()
    service = ResourceAnnotationService(
        annotation_repository=repo.annotation_repository,
        fusion_repository=repo.fusion_repository,
        translocation_repository=repo.translocation_repository,
        copy_number_variant_repository=repo.copy_number_variant_repository,
        variant_repository=repo.variant_repository,
    )

    resource = service.create_annotation(
        form_data={"text": "note", "translocpoints": "1:100^2:200"},
        target_id="tl-1",
        get_variant_nomenclature_fn=_nomenclature,
        create_comment_doc_fn=_comment_doc,
    )

    assert resource == "translocation_comment"
    assert repo.translocation_repository.comments[0][0] == "tl-1"


def test_resource_classification_service_supports_fusion_bulk_tiering(monkeypatch):
    """Test resource classification service supports fusion bulk tiering.

    Returns:
        The function result.
    """
    repo = _RepoStub()
    service = _classification_service(repo)

    service.set_tier_bulk(
        sample={"_id": "S1", "asp_id": "assay", "environment": "production"},
        resource_type="fusion",
        resource_ids=["fus-1"],
        apply=True,
        class_num=2,
        create_annotation_text_fn=lambda gene, consequence, assay_group, gene_oncokb=None: (
            f"{gene}:{assay_group}"
        ),
        create_classified_variant_doc_fn=_classification_doc,
    )

    docs = repo.annotation_repository.inserted_bulk
    assert docs is not None
    assert len(docs) == 1
    assert docs[0]["nomenclature"] == "f"
    assert docs[0]["variant"] == "2:100^2:200"
    assert docs[0]["variant_data"]["gene1"] == "EML4"
    assert docs[0]["variant_data"]["gene2"] == "ALK"
    assert set(docs[0]["variant_data"]) == {"assay_group", "subpanel", "gene1", "gene2"}


def test_resource_classification_service_generates_text_only_for_tier_three_snvs():
    """Tier 3 SNV bulk classification creates one class and one narrative document."""
    repo = _RepoStub()
    service = _classification_service(repo)

    service.set_tier_bulk(
        sample={"_id": "S1", "asp_id": "assay", "environment": "production"},
        resource_type="small_variant",
        resource_ids=["var-1"],
        apply=True,
        class_num=3,
        create_annotation_text_fn=lambda gene, consequence, assay_group, gene_oncokb=None: (
            f"Tier III text for {gene}"
        ),
        create_classified_variant_doc_fn=_classification_doc,
    )

    docs = repo.annotation_repository.inserted_bulk
    assert docs is not None
    assert len(docs) == 2
    assert docs[0]["class"] == 3
    assert docs[0]["text"] is None
    assert docs[1]["text"] == "Tier III text for SRSF2"


def test_resource_classification_service_does_not_generate_text_for_other_snv_tiers():
    """Non-Tier 3 SNV bulk classification persists only the classification document."""
    repo = _RepoStub()
    service = _classification_service(repo)

    def unexpected_text_generation(*args, **kwargs):
        raise AssertionError("Non-Tier 3 classification must not generate narrative text")

    service.set_tier_bulk(
        sample={"_id": "S1", "asp_id": "assay", "environment": "production"},
        resource_type="small_variant",
        resource_ids=["var-1"],
        apply=True,
        class_num=2,
        create_annotation_text_fn=unexpected_text_generation,
        create_classified_variant_doc_fn=_classification_doc,
    )

    docs = repo.annotation_repository.inserted_bulk
    assert docs is not None
    assert len(docs) == 1
    assert docs[0]["class"] == 2
    assert docs[0]["text"] is None


def test_non_tier_three_removal_does_not_delete_tier_three_narrative():
    """Removing another tier must not match the approved Tier 3 narrative document."""
    repo = _RepoStub()
    service = _classification_service(repo)

    def unexpected_text_generation(*args, **kwargs):
        raise AssertionError("Non-Tier 3 removal must not generate narrative text")

    service.set_tier_bulk(
        sample={"_id": "S1", "asp_id": "assay", "environment": "production"},
        resource_type="small_variant",
        resource_ids=["var-1"],
        apply=False,
        class_num=2,
        create_annotation_text_fn=unexpected_text_generation,
        create_classified_variant_doc_fn=_classification_doc,
    )

    assert len(repo.annotation_repository.deleted) == 1
    assert repo.annotation_repository.deleted[0]["class_num"] == 2
    assert repo.annotation_repository.deleted[0]["annotation_text"] is None


def test_resource_classification_service_supports_translocation_bulk_removal(monkeypatch):
    """Test resource classification service supports translocation bulk removal.

    Returns:
        The function result.
    """
    repo = _RepoStub()
    service = _classification_service(repo)

    service.set_tier_bulk(
        sample={
            "_id": "S1",
            "asp_id": "assay",
            "environment": "production",
            "subpanel_id": "solid",
        },
        resource_type="translocation",
        resource_ids=["tl-1"],
        apply=False,
        class_num=3,
        create_annotation_text_fn=lambda gene, consequence, assay_group, gene_oncokb=None: (
            f"{gene}:{assay_group}"
        ),
        create_classified_variant_doc_fn=_classification_doc,
    )

    assert len(repo.annotation_repository.deleted) == 1
    assert repo.annotation_repository.deleted[0]["nomenclature"] == "t"
    assert repo.annotation_repository.deleted[0]["variant"] == "1:100^2:200"
