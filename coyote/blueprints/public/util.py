#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#


from collections import defaultdict
from flask import current_app as app
from coyote.extensions import store
from typing import Optional, List, Dict, Any, Tuple, Set
import yaml


class PublicUtility:
    """
    PublicUtility provides static utility methods for processing data.
    """

    @staticmethod
    def _catalog() -> Dict[str, Any]:
        """
        Load and cache the catalog YAML file.
        """
        if not hasattr(app, "_catalog_cache"):
            path = app.config.get("CATALOG_YAML_PATH", "config/catalog.yaml")
            with open(path, "r", encoding="utf-8") as f:
                app._catalog_cache = yaml.safe_load(f) or {}
        return app._catalog_cache or {}

    @staticmethod
    def _norm_modality(dna_rna: Optional[str]) -> Optional[str]:
        if not dna_rna:
            return None
        v = dna_rna.strip().lower()
        if v in ("dna", "rna"):
            return v
        # Be forgiving: "DNA " / "rna" / "Dna"
        return "dna" if v.startswith("dna") else ("rna" if v.startswith("rna") else None)

    @staticmethod
    def _get_assay_def(assay_key: str) -> Dict[str, Any]:
        cat = PublicUtility._catalog()
        assays = cat.get("assays", {})
        return assays.get(assay_key, {})

    @staticmethod
    def _list_assays(modality: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of assay cards: key, display_name, description, available modalities, counts.
        If modality is provided ('dna'|'rna'), only includes assays that have that modality with at least one diagnosis.
        """
        cat = PublicUtility._catalog()
        out: List[Dict[str, Any]] = []
        for key, a in (cat.get("assays") or {}).items():
            mods = a.get("modalities") or {}
            dna = mods.get("dna") or {}
            rna = mods.get("rna") or {}
            dna_dx = list(dna.get("diagnoses") or [])
            rna_dx = list(rna.get("diagnoses") or [])
            if modality == "dna" and not dna_dx:
                continue
            if modality == "rna" and not rna_dx:
                continue
            out.append(
                {
                    "key": key,
                    "display_name": a.get("display_name", key.replace("_", " ").title()),
                    "description": a.get("description", ""),
                    "technology": a.get("technology", "Panels"),
                    "modalities": {
                        "dna": {"has": bool(dna_dx), "dx_count": len(dna_dx)},
                        "rna": {"has": bool(rna_dx), "dx_count": len(rna_dx)},
                    },
                    "order": a.get("order", 999),
                }
            )
        return sorted(out, key=lambda x: x["order"])

    @staticmethod
    def _get_diagnosis_cards(assay_key: str, modality: str) -> List[Dict[str, Any]]:
        """
        Cards for the two columns (DNA / RNA) on the assay page.
        Pulls per-dx structured bits from YAML and short description from dx root.
        """
        a = PublicUtility._get_assay_def(assay_key)
        dx_keys = list(((a.get("modalities") or {}).get(modality) or {}).get("diagnoses") or [])
        cat = PublicUtility._catalog()
        dxdict = cat.get("diagnoses") or {}
        cards: List[Dict[str, Any]] = []
        for k in dx_keys:
            dx = dxdict.get(k) or {}
            bm = (dx.get("by_modality") or {}).get(modality) or {}
            cards.append(
                {
                    "key": k,
                    "label": dx.get("display_name", k.upper()),
                    "description": dx.get("description", ""),
                    "tat": bm.get("tat", ""),
                    "analysis_includes": bm.get("analysis_includes", []),
                    "sample_types": bm.get("sample_types", []),
                    "sample_modes": bm.get("sample_modes", []),
                    "methodology": bm.get("methodology", []),
                }
            )
        order_map = {k: (dxdict.get(k) or {}).get("order", 999) for k in dx_keys}
        return sorted(cards, key=lambda c: order_map.get(c["key"], 999))

    @staticmethod
    def _asp_ids_for_assay_modality(assay_key: str, modality: str) -> List[str]:
        a = PublicUtility._get_assay_def(assay_key)
        return list(((a.get("modalities") or {}).get(modality) or {}).get("asp_ids") or [])

    @staticmethod
    def _asp_ids_for_dx(assay_key: str, modality: str, dx_key: str) -> List[str]:
        cat = PublicUtility._catalog()
        dx = (cat.get("diagnoses") or {}).get(dx_key) or {}
        bm = (dx.get("by_modality") or {}).get(modality) or {}
        return list((bm.get("asp_bindings") or {}).get(assay_key) or [])

    @staticmethod
    def _union_asp_genes(asp_ids: List[str]) -> Tuple[List[str], Set[str]]:
        u: Set[str] = set()
        germ_u: Set[str] = set()
        for aid in asp_ids:
            g, germ = store.asp_handler.get_asp_genes(aid)
            u.update(g)
            germ_u.update(germ)
        return sorted(u), germ_u

    @staticmethod
    def _get_public_overview_for_asp(asp_id: str) -> Dict[str, Any]:
        try:
            asp = store.asps.find_one({"assay_name": asp_id}, {"public_overview": 1}) or {}
            return asp.get("public_overview") or {}
        except Exception:
            return {}

    @staticmethod
    def _get_public_overview_for_dx(dx_key: str) -> Dict[str, Any]:
        try:
            dx = store.isgl.find_one({"_id": dx_key}, {"public_overview": 1}) or {}
            return dx.get("public_overview") or {}
        except Exception:
            return {}

    @staticmethod
    def _compose_assay_overview(
        assay_key: Optional[str], modality: Optional[str], dx_key: Optional[str]
    ) -> Dict[str, Any]:
        """
        Build the assay_overview dict the template expects by blending:
          - YAML long/short text (assay description; DX structured bits)
          - DB 'public_overview' blocks from ASP (first ASP bound) and ISGL (if dx)
        """
        cat = PublicUtility._catalog()
        asp_block: Dict[str, Any] = {}
        dx_block: Dict[str, Any] = {}
        links: List[Tuple[str, str]] = []

        # From YAML (assay family description on ASP level)
        if assay_key:
            a = (cat.get("assays") or {}).get(assay_key) or {}
            # YAML gives generic family description
            asp_block.setdefault("description", a.get("description", ""))

        # Pull first bound ASP overview (if any)
        if assay_key and modality:
            asp_ids = PublicUtility._asp_ids_for_assay_modality(assay_key, modality)
            if asp_ids:
                pov = PublicUtility._get_public_overview_for_asp(asp_ids[0])
                if pov:
                    asp_block = {
                        "description": pov.get("description", asp_block.get("description", "")),
                        "sequencing": pov.get("sequencing", ""),
                        "tat": pov.get("tat", ""),
                        "sample_type": pov.get("sample_type", ""),
                        "includes": pov.get("includes", ""),
                    }
                    links = pov.get("links", []) or []

        # DX specific (YAML by_modality + ISGL.public_overview)
        if dx_key and modality:
            dx_yaml = ((cat.get("diagnoses") or {}).get(dx_key) or {}).get("by_modality", {}).get(
                modality, {}
            ) or {}
            dx_block = {
                "description": cat.get("diagnoses", {}).get(dx_key, {}).get("description", {}),
                "sequencing": dx_yaml.get("methodology", []),
                "tat": dx_yaml.get("tat", ""),
                "sample_type": ", ".join(dx_yaml.get("sample_types", [])),
                "includes": ", ".join(dx_yaml.get("analysis_includes", [])),
            }

        return {
            "asp": {
                "description": asp_block.get("description", ""),
                "sequencing": asp_block.get("sequencing", ""),
                "tat": asp_block.get("tat", ""),
                "sample_type": asp_block.get("sample_type", ""),
                "includes": asp_block.get("includes", ""),
            },
            "dx": {
                "description": dx_block.get("description", ""),
                "sequencing": dx_block.get("sequencing", ""),
                "tat": dx_block.get("tat", ""),
                "sample_type": dx_block.get("sample_type", ""),
                "includes": dx_block.get("includes", ""),
            },
            "links": links,
        }
