from __future__ import annotations

from coyote.application.interpretation.annotation_enrichment import add_alt_class


def test_add_alt_class_ignores_null_classification():
    class Repo:
        @staticmethod
        def get_additional_classifications(_variant, _assay_group, _diagnosis, **_kwargs):
            return [{"class": None, "author": "u", "time_created": "now"}]

    variant = add_alt_class({}, "hematology", "base", annotation_repository=Repo())

    assert variant["additional_classification"] is None
