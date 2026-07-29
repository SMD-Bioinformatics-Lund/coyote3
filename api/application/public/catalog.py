"""Public assay catalog application service used by FastAPI public routes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from api.config.constants import ASP_CATEGORY_OPTIONS, DEFAULT_ENVIRONMENT, SUBPANEL_BASE_ID
from api.config.paths import ASSAY_CATALOG_PATH


class PublicCatalogService:
    """Provide public catalog workflows."""

    DEFAULT_ENV = DEFAULT_ENVIRONMENT

    @classmethod
    def from_store(cls, store: Any) -> "PublicCatalogService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            hgnc_repository=store.hgnc_repository,
            gene_list_repository=store.gene_list_repository,
            sample_repository=store.sample_repository,
            vep_metadata_repository=store.vep_metadata_repository,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        hgnc_repository: Any,
        gene_list_repository: Any,
        sample_repository: Any,
        vep_metadata_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.hgnc_repository = hgnc_repository
        self.gene_list_repository = gene_list_repository
        self.sample_repository = sample_repository
        self.vep_metadata_repository = vep_metadata_repository

    def observed_software_versions(self) -> dict[str, object]:
        """Return bounded software versions observed across ready samples."""
        return self.sample_repository.get_observed_software_versions()

    def observed_reference_versions(self) -> dict[str, object]:
        """Return observed sample and configured VEP metadata versions."""
        return {
            "sample_database_versions": self.sample_repository.get_observed_database_versions(),
            "vep_metadata": self.vep_metadata_repository.list_versions(),
        }

    @staticmethod
    def _catalog_overlay_path() -> Path:
        return ASSAY_CATALOG_PATH

    @classmethod
    def _load_catalog_overlay(cls) -> dict[str, Any]:
        path = cls._catalog_overlay_path()
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _overlay_modalities(overlay: dict[str, Any]) -> dict[str, Any]:
        modalities = overlay.get("modalities")
        return modalities if isinstance(modalities, dict) else {}

    @staticmethod
    def _overlay_categories(overlay: dict[str, Any]) -> list[dict[str, Any]]:
        direct = overlay.get("categories")
        if isinstance(direct, list):
            return [item for item in direct if isinstance(item, dict)]

        out: list[dict[str, Any]] = []
        modalities = (
            overlay.get("modalities") if isinstance(overlay.get("modalities"), dict) else {}
        )
        for modality_key, modality in modalities.items():
            categories = modality.get("categories") if isinstance(modality, dict) else None
            if isinstance(categories, list):
                for category in categories:
                    if isinstance(category, dict):
                        out.append({"modality": modality_key, **category})
            elif isinstance(categories, dict):
                for category_key, category in categories.items():
                    if isinstance(category, dict):
                        out.append(
                            {"modality": modality_key, "category_key": category_key, **category}
                        )
        return out

    @classmethod
    def _category_overlay(
        cls,
        overlay: dict[str, Any],
        *,
        asp_id: str,
        subpanel_id: str,
        aspc_id: str | None,
        catalog_id: str,
    ) -> dict[str, Any]:
        for item in cls._overlay_categories(overlay):
            item_asp = str(item.get("asp_id") or "").strip()
            item_subpanel = (
                str(item.get("subpanel_id") or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID
            )
            item_aspc = str(item.get("aspc_id") or "").strip()
            item_catalog = str(item.get("catalog_id") or item.get("category_key") or "").strip()
            if item_catalog and item_catalog == catalog_id:
                return item
            if item_asp == asp_id and item_subpanel == subpanel_id:
                return item
            if aspc_id and item_aspc == aspc_id:
                return item
        return {}

    @staticmethod
    def _gene_list_overlay(category_overlay: dict[str, Any], isgl_id: str) -> dict[str, Any]:
        for item in category_overlay.get("gene_lists") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("isgl_id") or item.get("key") or "").strip()
            if item_id == isgl_id:
                return item
        return {}

    @staticmethod
    def _prefer_overlay(
        category_overlay: dict[str, Any], catalog: dict[str, Any], *keys: str
    ) -> Any:
        for key in keys:
            if key in category_overlay and category_overlay.get(key) not in (None, ""):
                return category_overlay.get(key)
            if key in catalog and catalog.get(key) not in (None, ""):
                return catalog.get(key)
        return None

    def load_catalog(self) -> Dict[str, Any]:
        """Build the public assay catalog from active ASP, ASPC, and ISGL documents.

        Returns:
            Dict[str, Any]: Catalog data in the UI contract shape.
        """
        active_asps = self.assay_panel_repository.get_all_asps(is_active=True) or []
        active_isgls = self.gene_list_repository.get_all_isgl(
            is_active=True, is_public=True, adhoc=False
        )
        overlay = self._load_catalog_overlay()
        overlay_modalities = self._overlay_modalities(overlay)
        isgls_by_asp = self._group_isgls_by_asp_and_subpanel(active_isgls)
        nav_groups = self._nav_groups_from_asps(active_asps)

        if overlay_modalities:
            modalities = self._catalog_from_overlay_modalities(
                overlay_modalities=overlay_modalities,
                active_asps=active_asps,
                active_isgls=active_isgls,
            )
            order = self._overlay_order(overlay, modalities)
            return {
                "version": overlay.get("version") or "collections",
                "last_updated": overlay.get("last_updated")
                or datetime.now(timezone.utc).isoformat(),
                "maintainer": overlay.get("maintainer") or "Coyote3",
                "header": overlay.get("header") or "Assay Catalog",
                "description": overlay.get("description")
                or "Catalog generated from center YAML metadata and active collection documents.",
                "layout": {"order": order},
                "modalities": modalities,
                "nav_groups": nav_groups,
            }

        modalities: dict[str, Any] = {}
        for category in ASP_CATEGORY_OPTIONS:
            category_asps = [
                dict(asp)
                for asp in active_asps
                if str(asp.get("asp_category") or "").strip().lower() == category
            ]
            if not category_asps:
                continue
            categories: dict[str, Any] = {}
            grouped_for_nav: dict[tuple[str, str], dict[str, Any]] = {}
            for asp in sorted(
                category_asps,
                key=lambda item: (
                    self._family_bucket(item),
                    str(item.get("asp_group") or ""),
                    str(item.get("display_name") or item.get("asp_id") or ""),
                ),
            ):
                asp_id = str(asp.get("asp_id") or "").strip()
                if not asp_id:
                    continue
                family = self._family_bucket(asp)
                assay_group = str(asp.get("asp_group") or "unassigned").strip() or "unassigned"
                aspcs = self.assay_configuration_repository.get_active_aspcs_for_asp(
                    asp_id, self.DEFAULT_ENV
                )
                if not aspcs:
                    aspcs = [None]
                for aspc in aspcs:
                    catalog = self._aspc_catalog(aspc)
                    if aspc and not catalog.get("is_public", True):
                        continue
                    subpanel_id = self._aspc_subpanel_id(aspc)
                    category_key = self._category_key(asp, aspc)
                    categories[category_key] = self._category_from_asp(
                        asp=asp,
                        aspc=aspc,
                        family=family,
                        assay_group=assay_group,
                        gene_lists=self._isgls_for_catalog_subpanel(
                            isgls_by_asp.get(asp_id, {}), subpanel_id
                        ),
                        overlay=overlay,
                    )
                nav_key = (family, assay_group)
                grouped_for_nav.setdefault(
                    nav_key,
                    {
                        "category": category,
                        "family": family,
                        "assay_group": assay_group,
                        "label": f"{self._title(family)} {self._title(assay_group)}",
                        "asp_ids": [],
                        "sample_query": {
                            "panel_type": category,
                            "panel_tech": family,
                            "assay_group": assay_group,
                        },
                    },
                )["asp_ids"].append(asp_id)

            modalities[category] = {
                "label": (overlay.get("modalities") or {}).get(category, {}).get("label")
                if isinstance((overlay.get("modalities") or {}).get(category), dict)
                else category.upper(),
                "title": (overlay.get("modalities") or {}).get(category, {}).get("title")
                if isinstance((overlay.get("modalities") or {}).get(category), dict)
                else category.upper(),
                "description": (
                    (overlay.get("modalities") or {}).get(category, {}).get("description")
                    if isinstance((overlay.get("modalities") or {}).get(category), dict)
                    else f"{category.upper()} asp_ids grouped by assay family and assay group."
                ),
                "categories": categories,
                "sample_groups": sorted(
                    grouped_for_nav.values(),
                    key=lambda item: (item["family"], item["assay_group"]),
                ),
            }

        order = [category for category in ASP_CATEGORY_OPTIONS if category in modalities]
        return {
            "version": overlay.get("version") or "collections",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "maintainer": overlay.get("maintainer") or "Coyote3",
            "header": overlay.get("header") or "Assay Catalog",
            "description": overlay.get("description")
            or "Catalog generated from active ASP, ASPC, and public ISGL collection documents with optional center metadata from YAML.",
            "layout": {"order": order},
            "modalities": modalities,
            "nav_groups": nav_groups,
        }

    @staticmethod
    def _overlay_order(overlay: dict[str, Any], modalities: dict[str, Any]) -> list[str]:
        layout = overlay.get("layout") if isinstance(overlay.get("layout"), dict) else {}
        configured = layout.get("order") if isinstance(layout.get("order"), list) else []
        ordered = [str(item) for item in configured if str(item) in modalities]
        ordered.extend(key for key in modalities if key not in ordered)
        return ordered

    def _nav_groups_from_asps(self, active_asps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for asp in active_asps or []:
            asp_id = str(asp.get("asp_id") or "").strip()
            if not asp_id:
                continue
            category = str(asp.get("asp_category") or "").strip().lower() or "assay"
            family = self._family_bucket(asp)
            assay_group = str(asp.get("asp_group") or "unassigned").strip() or "unassigned"
            grouped.setdefault(
                (category, family, assay_group),
                {
                    "category": category,
                    "family": family,
                    "assay_group": assay_group,
                    "label": f"{self._title(family)} {self._title(assay_group)}",
                    "asp_ids": [],
                    "sample_query": {
                        "panel_type": category,
                        "panel_tech": family,
                        "assay_group": assay_group,
                    },
                },
            )["asp_ids"].append(asp_id)
        return sorted(
            grouped.values(),
            key=lambda item: (item["category"], item["family"], item["assay_group"]),
        )

    def _catalog_from_overlay_modalities(
        self,
        *,
        overlay_modalities: dict[str, Any],
        active_asps: list[dict[str, Any]],
        active_isgls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        asp_by_id = {str(asp.get("asp_id") or "").strip(): dict(asp) for asp in active_asps or []}
        isgl_by_id = {
            str(isgl.get("isgl_id") or "").strip(): dict(isgl) for isgl in active_isgls or []
        }
        modalities: dict[str, Any] = {}

        for modality_key, modality_overlay in overlay_modalities.items():
            if not isinstance(modality_overlay, dict):
                continue
            categories: dict[str, Any] = {}
            raw_categories = modality_overlay.get("categories")
            category_items = (
                raw_categories.items()
                if isinstance(raw_categories, dict)
                else enumerate(raw_categories or [])
            )
            for raw_key, raw_category in category_items:
                if not isinstance(raw_category, dict):
                    continue
                category_key = str(raw_category.get("category_key") or raw_key)
                categories[category_key] = self._overlay_category_payload(
                    category_key=category_key,
                    category_overlay=raw_category,
                    asp_by_id=asp_by_id,
                    isgl_by_id=isgl_by_id,
                )

            modalities[str(modality_key)] = {
                **{key: value for key, value in modality_overlay.items() if key != "categories"},
                "label": modality_overlay.get("label") or self._title(modality_key),
                "title": modality_overlay.get("title")
                or modality_overlay.get("label")
                or self._title(modality_key),
                "description": modality_overlay.get("description") or "",
                "categories": categories,
                "sample_groups": [],
            }
        return modalities

    def _overlay_category_payload(
        self,
        *,
        category_key: str,
        category_overlay: dict[str, Any],
        asp_by_id: dict[str, dict[str, Any]],
        isgl_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        asp_id = str(category_overlay.get("asp_id") or "").strip()
        asp = asp_by_id.get(asp_id, {})
        aspc = self._overlay_aspc(category_overlay, asp_id)
        subpanel_id = (
            str(category_overlay.get("subpanel_id") or self._aspc_subpanel_id(aspc)).strip()
            or SUBPANEL_BASE_ID
        )
        gene_lists = [
            self._overlay_gene_list_payload(item, category_overlay, isgl_by_id)
            for item in (category_overlay.get("gene_lists") or [])
            if isinstance(item, dict)
        ]
        gene_lists = [item for item in gene_lists if item]
        asp_details = {
            "platform": asp.get("platform"),
            "read_length": asp.get("read_length"),
            "read_mode": asp.get("read_mode"),
            "covered_genes_count": asp.get("covered_genes_count"),
            "germline_genes_count": asp.get("germline_genes_count"),
        }
        family = (
            self._family_bucket(asp)
            if asp
            else str(category_overlay.get("family") or category_overlay.get("asp_family") or "")
        )
        assay_group = str(
            category_overlay.get("assay_group") or asp.get("asp_group") or category_key
        ).strip()
        analysis = category_overlay.get("analysis") or self._aspc_available_analysis(aspc)

        return {
            **category_overlay,
            "catalog_id": category_overlay.get("catalog_id") or category_key,
            "label": category_overlay.get("label") or category_overlay.get("title") or category_key,
            "title": category_overlay.get("title") or category_overlay.get("label") or category_key,
            "description": category_overlay.get("description") or asp.get("description") or "",
            "subheading": category_overlay.get("subheading"),
            "family": family,
            "assay_group": assay_group,
            "asp_id": asp_id or None,
            "aspc_id": category_overlay.get("aspc_id") or (aspc or {}).get("aspc_id"),
            "aspc_ids": category_overlay.get("aspc_ids") or {},
            "subpanel_id": subpanel_id,
            "asp": asp_details,
            "input_material": category_overlay.get("input_material") or asp.get("asp_category"),
            "tat": category_overlay.get("tat"),
            "sample_modes": category_overlay.get("sample_modes") or [],
            "analysis": analysis or [],
            "report_sections": category_overlay.get("report_sections")
            or self._aspc_report_sections(aspc),
            "clinical_indications": category_overlay.get("clinical_indications") or [],
            "limitations": category_overlay.get("limitations"),
            "public_notes": category_overlay.get("public_notes"),
            "sample_query": {
                "panel_type": asp.get("asp_category"),
                "panel_tech": family,
                "assay_group": assay_group,
            },
            "gene_lists": gene_lists,
        }

    def _overlay_aspc(self, category_overlay: dict[str, Any], asp_id: str) -> dict[str, Any] | None:
        aspc_id = str(category_overlay.get("aspc_id") or "").strip()
        if aspc_id:
            return self.assay_configuration_repository.get_aspc_with_id(aspc_id)
        aspc_ids = (
            category_overlay.get("aspc_ids")
            if isinstance(category_overlay.get("aspc_ids"), dict)
            else {}
        )
        if aspc_ids:
            return self._fetch_aspc(aspc_ids, self.DEFAULT_ENV)
        if asp_id:
            aspcs = self.assay_configuration_repository.get_active_aspcs_for_asp(
                asp_id, self.DEFAULT_ENV
            )
            return aspcs[0] if aspcs else None
        return None

    @staticmethod
    def _overlay_gene_list_payload(
        item: dict[str, Any],
        category_overlay: dict[str, Any],
        isgl_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        isgl_id = str(item.get("isgl_id") or item.get("key") or "").strip()
        if not isgl_id and not item.get("label"):
            return {}
        isgl = isgl_by_id.get(isgl_id, {})
        return {
            **item,
            "key": isgl_id,
            "catalog_id": item.get("catalog_id") or isgl_id,
            "label": item.get("label") or isgl.get("displayname") or isgl.get("name") or isgl_id,
            "description": item.get("description") or isgl.get("description") or "",
            "diagnosis": item.get("diagnosis") or isgl.get("diagnosis") or [],
            "subpanel_id": item.get("subpanel_id")
            or isgl.get("subpanel_id")
            or category_overlay.get("subpanel_id")
            or SUBPANEL_BASE_ID,
            "list_type": item.get("list_type") or isgl.get("list_type") or [],
            "tat": item.get("tat") or category_overlay.get("tat"),
            "input_material": item.get("input_material") or category_overlay.get("input_material"),
            "sample_modes": item.get("sample_modes") or category_overlay.get("sample_modes"),
            "analysis": item.get("analysis") or category_overlay.get("analysis"),
        }

    def modalities_order(self) -> List[str]:
        """Return the display order for catalog modalities.

        Returns:
            List[str]: Ordered modality keys.
        """
        catalog = self.load_catalog()
        order = (catalog.get("layout") or {}).get("order") or []
        return order or list((catalog.get("modalities") or {}).keys())

    def normalize_mod(self, mod: Optional[str]) -> Optional[str]:
        """Normalize modality aliases to catalog keys.

        Args:
            mod: Raw modality value from the request.

        Returns:
            Optional[str]: Canonical modality key when recognized.
        """
        if not mod:
            return None
        catalog_modalities = self.load_catalog().get("modalities") or {}
        if mod in catalog_modalities:
            return mod
        for key in catalog_modalities:
            if str(key).lower() == str(mod).strip().lower():
                return str(key)
        value = (mod or "").strip().lower()
        if value in ASP_CATEGORY_OPTIONS:
            return value
        alias_targets = {
            "whole genome sequencing": "WGS",
            "whole-genome-sequencing": "WGS",
            "wholegenomesequencing": "WGS",
            "wgs": "WGS",
            "whole transcriptome sequencing": "WTS",
            "whole-transcriptome-sequencing": "WTS",
            "wholetranscriptomesequencing": "WTS",
            "wts": "WTS",
            "panel": "GenePanels",
            "panels": "GenePanels",
            "gene panel": "GenePanels",
            "gene-panel": "GenePanels",
            "gene panels": "GenePanels",
            "gene-panels": "GenePanels",
            "genepanel": "GenePanels",
            "genepanels": "GenePanels",
        }
        alias_target = alias_targets.get(value)
        if alias_target:
            for key in catalog_modalities:
                if str(key).lower() == alias_target.lower():
                    return str(key)
            if alias_target == "WGS" and "dna" in catalog_modalities:
                return "dna"
            if alias_target == "WTS" and "rna" in catalog_modalities:
                return "rna"
            if alias_target == "GenePanels" and "dna" in catalog_modalities:
                return "dna"
        if value.upper() in {"DNA", "RNA"}:
            return value.lower()
        return None

    def modality_block(self, mod: str) -> Optional[Dict[str, Any]]:
        """Return the catalog block for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Optional[Dict[str, Any]]: Catalog block for the modality.
        """
        return (self.load_catalog().get("modalities") or {}).get(mod)

    def categories_for(self, mod: str) -> List[Dict[str, Any]]:
        """Return category entries for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            List[Dict[str, Any]]: Category descriptors for the modality.
        """
        modality = self.modality_block(mod) or {}
        categories = modality.get("categories") or {}
        out: List[Dict[str, Any]] = []
        for key, category in categories.items():
            out.append(
                {
                    "catalog_id": category.get("catalog_id") or key,
                    "label": category.get("label") or key,
                    "node": category,
                }
            )
        return out

    def category_def(self, mod: str, cat_id: str) -> Optional[Dict[str, Any]]:
        """Return the catalog definition for a modality category.

        Args:
            mod: Canonical modality key.
            cat_id: Category identifier to resolve.

        Returns:
            Optional[Dict[str, Any]]: Category definition when found.
        """
        modality = self.modality_block(mod) or {}
        categories = modality.get("categories") or {}
        for key, category in categories.items():
            if cat_id == (category.get("catalog_id") or key) or cat_id == key:
                return category
        return None

    def _fetch_aspc(self, aspc_ids: Optional[Dict[str, str]], env: str) -> Optional[Dict[str, Any]]:
        """Resolve an assay-config document for a target environment.

        Args:
            aspc_ids: Environment-to-assay-config mapping.
            env: Environment to resolve.

        Returns:
            Optional[Dict[str, Any]]: Assay-config document when available.
        """
        if not aspc_ids:
            return None
        aspc_id = aspc_ids.get(env)
        if not aspc_id:
            return None
        return self.assay_configuration_repository.get_aspc_with_id(aspc_id)

    @staticmethod
    def _title(value: object) -> str:
        return str(value or "").replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _family_bucket(asp: dict[str, Any]) -> str:
        family = str(asp.get("asp_family") or "").strip().lower()
        if family.startswith("panel"):
            return "panel"
        return family or "assay"

    @staticmethod
    def _aspc_subpanel_id(aspc: dict[str, Any] | None) -> str:
        return str((aspc or {}).get("subpanel_id") or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID

    @staticmethod
    def _aspc_catalog(aspc: dict[str, Any] | None) -> dict[str, Any]:
        catalog = (aspc or {}).get("catalog")
        return catalog if isinstance(catalog, dict) else {}

    @classmethod
    def _category_key(cls, asp: dict[str, Any], aspc: dict[str, Any] | None = None) -> str:
        return "::".join(
            [
                cls._family_bucket(asp),
                str(asp.get("asp_group") or "unassigned").strip() or "unassigned",
                str(asp.get("asp_id") or "").strip(),
                cls._aspc_subpanel_id(aspc),
            ]
        )

    @staticmethod
    def _unique(values: list[Any]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    @classmethod
    def _aspc_available_analysis(cls, aspc: dict[str, Any] | None) -> list[str]:
        if not aspc:
            return []
        reporting = aspc.get("reporting") if isinstance(aspc.get("reporting"), dict) else {}
        return cls._unique(
            list(reporting.get("analysis") or [])
            + list(aspc.get("analysis_types") or [])
            + list(reporting.get("report_sections") or [])
        )

    @classmethod
    def _aspc_report_sections(cls, aspc: dict[str, Any] | None) -> list[str]:
        if not aspc:
            return []
        reporting = aspc.get("reporting") if isinstance(aspc.get("reporting"), dict) else {}
        return cls._unique(list(reporting.get("report_sections") or []))

    def _category_from_asp(
        self,
        *,
        asp: dict[str, Any],
        aspc: dict[str, Any] | None,
        family: str,
        assay_group: str,
        gene_lists: list[dict[str, Any]],
        overlay: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        asp_id = str(asp.get("asp_id") or "")
        subpanel_id = self._aspc_subpanel_id(aspc)
        catalog = self._aspc_catalog(aspc)
        catalog_id = self._category_key(asp, aspc)
        category_overlay = self._category_overlay(
            overlay or {},
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            aspc_id=aspc.get("aspc_id") if aspc else None,
            catalog_id=catalog_id,
        )
        aspc_display_name = aspc.get("display_name") if aspc else None
        display_name = (
            category_overlay.get("title")
            or category_overlay.get("label")
            or catalog.get("title")
            or aspc_display_name
            or asp.get("display_name")
            or asp.get("asp_id")
            or asp_id
        )
        if subpanel_id != SUBPANEL_BASE_ID and catalog.get("title") is None:
            display_name = f"{display_name} - {self._title(subpanel_id)}"
        list_entries = [
            {
                "key": asp_id,
                "catalog_id": asp_id,
                "label": category_overlay.get("covered_genes_label") or "All covered genes",
                "description": category_overlay.get("covered_genes_description")
                or f"All genes targeted by {display_name}.",
                "list_type": ["covered_genes"],
                "tat": category_overlay.get("tat"),
            }
        ]
        for isgl in gene_lists:
            isgl_id = str(isgl.get("isgl_id") or "").strip()
            if not isgl_id:
                continue
            list_overlay = self._gene_list_overlay(category_overlay, isgl_id)
            list_entries.append(
                {
                    "key": isgl_id,
                    "catalog_id": isgl_id,
                    "label": list_overlay.get("label")
                    or isgl.get("displayname")
                    or isgl.get("name")
                    or isgl_id,
                    "description": list_overlay.get("description") or isgl.get("description") or "",
                    "diagnosis": isgl.get("diagnosis") or [],
                    "subpanel_id": isgl.get("subpanel_id") or SUBPANEL_BASE_ID,
                    "list_type": isgl.get("list_type") or [],
                    "tat": list_overlay.get("tat") or category_overlay.get("tat"),
                    "input_material": list_overlay.get("input_material")
                    or category_overlay.get("input_material"),
                    "sample_modes": list_overlay.get("sample_modes")
                    or category_overlay.get("sample_modes"),
                    "analysis": list_overlay.get("analysis"),
                }
            )
        return {
            "catalog_id": catalog_id,
            "label": display_name,
            "title": display_name,
            "description": self._prefer_overlay(category_overlay, catalog, "description")
            or (aspc or {}).get("description")
            or asp.get("description")
            or "",
            "subheading": self._prefer_overlay(category_overlay, catalog, "subheading"),
            "family": family,
            "assay_group": assay_group,
            "asp_id": asp_id,
            "aspc_id": aspc.get("aspc_id") if aspc else None,
            "subpanel_id": subpanel_id,
            "asp": {
                "platform": asp.get("platform"),
                "read_length": asp.get("read_length"),
                "read_mode": asp.get("read_mode"),
                "covered_genes_count": asp.get("covered_genes_count"),
                "germline_genes_count": asp.get("germline_genes_count"),
            },
            "input_material": self._prefer_overlay(category_overlay, catalog, "input_material")
            or asp.get("asp_category"),
            "tat": self._prefer_overlay(category_overlay, catalog, "tat"),
            "sample_modes": self._prefer_overlay(category_overlay, catalog, "sample_modes")
            or ["paired", "single"],
            "analysis": category_overlay.get("analysis") or self._aspc_available_analysis(aspc),
            "report_sections": self._aspc_report_sections(aspc),
            "clinical_indications": category_overlay.get("clinical_indications")
            or catalog.get("clinical_indications")
            or [],
            "limitations": category_overlay.get("limitations") or catalog.get("limitations"),
            "public_notes": category_overlay.get("public_notes") or catalog.get("public_notes"),
            "sample_query": {
                "panel_type": asp.get("asp_category"),
                "panel_tech": family,
                "assay_group": assay_group,
            },
            "gene_lists": list_entries,
        }

    @staticmethod
    def _group_isgls_by_asp_and_subpanel(
        isgls: list[dict[str, Any]],
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for isgl in isgls or []:
            subpanel_id = (
                str(isgl.get("subpanel_id") or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID
            )
            for asp_id in isgl.get("asp_ids") or []:
                key = str(asp_id or "").strip()
                if key:
                    grouped.setdefault(key, {}).setdefault(subpanel_id, []).append(dict(isgl))
        for asp_id, by_subpanel in grouped.items():
            for subpanel_id, values in by_subpanel.items():
                by_subpanel[subpanel_id] = sorted(
                    values,
                    key=lambda item: str(
                        item.get("displayname") or item.get("name") or item.get("isgl_id") or ""
                    ),
                )
        return grouped

    @staticmethod
    def _isgls_for_catalog_subpanel(
        isgls_by_subpanel: dict[str, list[dict[str, Any]]], subpanel_id: str
    ) -> list[dict[str, Any]]:
        selected = list(isgls_by_subpanel.get(subpanel_id, []))
        if subpanel_id != SUBPANEL_BASE_ID:
            selected.extend(isgls_by_subpanel.get(SUBPANEL_BASE_ID, []))
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for isgl in selected:
            isgl_id = str(isgl.get("isgl_id") or "").strip()
            if isgl_id and isgl_id not in seen:
                out.append(isgl)
                seen.add(isgl_id)
        return out

    def hydrate_category(
        self, mod: str, cat_id: str, gl_id: str | None = None, env: str = DEFAULT_ENV
    ) -> Optional[Dict[str, Any]]:
        """Hydrate a public catalog category with runtime metadata.

        Args:
            mod: Canonical modality key.
            cat_id: Category identifier to resolve.
            gl_id: Optional gene-list identifier to focus on.
            env: Environment to use for assay-config lookup.

        Returns:
            Optional[Dict[str, Any]]: Hydrated category payload when found.
        """
        node = self.category_def(mod, cat_id)
        if not node:
            return None

        gl_node: Dict[str, Any] = {}
        gene_lists = node.get("gene_lists") or []
        if gl_id:
            for gl in gene_lists:
                if gl_id == (gl.get("key") or gl.get("catalog_id")):
                    gl_node = gl
                    break

        asp_id = node.get("asp_id")
        aspc_id = node.get("aspc_id")
        aspc_ids = node.get("aspc_ids") or {}

        aspc = self.assay_configuration_repository.get_aspc_with_id(aspc_id) if aspc_id else None
        if not aspc and aspc_ids:
            aspc = self._fetch_aspc(aspc_ids, env)

        analysis = node.get("analysis", []) or []
        if aspc and not analysis:
            analysis = self._aspc_available_analysis(aspc)

        return {
            "catalog_id": node.get("catalog_id") or cat_id,
            "label": gl_node.get("label", node.get("label", cat_id)),
            "title": gl_node.get("label", node.get("title", node.get("label", cat_id))),
            "description": gl_node.get("description", node.get("description", "")),
            "subheading": gl_node.get("subheading", node.get("subheading")),
            "input_material": gl_node.get("input_material", node.get("input_material")),
            "tat": gl_node.get("tat", node.get("tat")),
            "sample_modes": gl_node.get("sample_modes", node.get("sample_modes", [])),
            "analysis": gl_node.get("analysis", analysis),
            "report_sections": node.get("report_sections") or self._aspc_report_sections(aspc),
            "asp_id": asp_id,
            "aspc_id": aspc_id,
            "aspc_ids": node.get("aspc_ids") or {},
            "subpanel_id": node.get("subpanel_id") or SUBPANEL_BASE_ID,
            "asp": node.get("asp"),
            "clinical_indications": node.get("clinical_indications") or [],
            "limitations": node.get("limitations"),
            "public_notes": node.get("public_notes"),
            "gene_lists": node.get("gene_lists", []) or [],
            "sample_query": node.get("sample_query"),
        }

    def hydrate_modality(self, mod: str) -> Dict[str, Any]:
        """Hydrate summary metadata for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Dict[str, Any]: Hydrated modality payload.
        """
        modality = self.modality_block(mod) or {}
        return {
            "title": modality.get("title") or modality.get("label", mod),
            "label": modality.get("label", mod),
            "description": modality.get("description", ""),
            "input_material": modality.get("input_material"),
            "tat": modality.get("tat"),
            "sample_modes": modality.get("sample_modes", []),
            "analysis": modality.get("analysis", []),
            "asp_id": modality.get("asp_id"),
            "asp": modality.get("asp"),
            "gene_lists": [],
        }

    def _covered_genes(self, asp_id: Optional[str]) -> Tuple[List[str], List[str]]:
        """Return covered and germline genes for an assay panel.

        Args:
            asp_id: Assay-panel identifier.

        Returns:
            Tuple[List[str], List[str]]: Covered and germline gene symbols.
        """
        if not asp_id:
            return [], []
        genes, germline = self.assay_panel_repository.get_asp_genes(asp_id)
        return list(genes or []), list(germline or [])

    def resolve_gene_table(
        self, asp_id: Optional[str], isgl_key: Optional[str]
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        """Resolve the public gene table for a category or genelist.

        Args:
            asp_id: Assay-panel identifier.
            isgl_key: Optional genelist identifier or assay-panel key.

        Returns:
            Tuple[str, List[Dict[str, Any]], Dict[str, int]]: Table kind, rows, and summary counts.
        """
        covered, germline = self._covered_genes(asp_id)

        if isgl_key == asp_id:
            show = sorted(set(covered))
            rows_raw = (
                list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
            )
            rows = self._merge_with_placeholders(show, rows_raw)
            return (
                "covered",
                rows,
                {
                    "total": len(show),
                    "isgl_total": len(show),
                    "covered_total": len(covered),
                    "germline_total": len(germline),
                },
            )

        if isgl_key:
            isgl = self.gene_list_repository.get_isgl(isgl_key) or {}
            isgl_genes = list(isgl.get("genes", []) or [])
            if covered:
                show = sorted(set(isgl_genes).intersection(set(covered)))
                mode = "overlap"
            else:
                show = sorted(set(isgl_genes))
                mode = "genelist"
            rows_raw = (
                list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
            )
            rows = self._merge_with_placeholders(show, rows_raw)
            return (
                mode,
                rows,
                {
                    "total": len(show),
                    "isgl_total": len(isgl_genes),
                    "covered_total": len(covered),
                    "germline_total": len(germline),
                },
            )

        show = sorted(set(covered))
        rows_raw = list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
        rows = self._merge_with_placeholders(show, rows_raw)
        return (
            "covered",
            rows,
            {
                "total": len(show),
                "covered_total": len(covered),
                "germline_total": len(germline),
            },
        )

    @staticmethod
    def _list_values(value: Any) -> list[str]:
        """Normalize scalar/list HGNC fields to strings."""
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        return []

    @classmethod
    def _row_symbols(cls, row: Dict[str, Any]) -> set[str]:
        """Return all symbols that should resolve to one HGNC row."""
        symbols = {
            str(row.get("hgnc_symbol") or row.get("symbol") or "").strip(),
        }
        symbols.update(cls._list_values(row.get("prev_symbol")))
        symbols.update(cls._list_values(row.get("alias_symbol")))
        return {symbol.upper() for symbol in symbols if symbol}

    @classmethod
    def _row_with_requested_symbol(
        cls, row: Dict[str, Any], requested_symbol: str
    ) -> Dict[str, Any]:
        """Attach panel-display and HGNC resolution metadata to a gene row."""
        requested = str(requested_symbol or "").strip()
        approved = str(row.get("hgnc_symbol") or row.get("symbol") or "").strip()
        prev = {symbol.upper() for symbol in cls._list_values(row.get("prev_symbol"))}
        aliases = {symbol.upper() for symbol in cls._list_values(row.get("alias_symbol"))}
        requested_upper = requested.upper()
        if approved and requested_upper == approved.upper():
            source = "approved_symbol"
        elif requested_upper in prev:
            source = "previous_symbol"
        elif requested_upper in aliases:
            source = "alias_symbol"
        else:
            source = "unresolved"
        return {
            **row,
            "display_symbol": requested or approved,
            "resolved_symbol": approved or requested,
            "hgnc_match_source": source,
            "symbol_changed": bool(approved and requested and approved.upper() != requested_upper),
        }

    @staticmethod
    def _hgnc_placeholder(symbol: str) -> Dict[str, Any]:
        """Return an explicit unresolved gene row without a fabricated HGNC ID.

        Args:
                symbol: Symbol.

        Returns:
                The  hgnc placeholder result.
        """
        cleaned = (symbol or "").strip()
        return {
            "_id": None,
            "hgnc_id": None,
            "hgnc_symbol": cleaned,
            "gene_name": "",
            "status": "Unresolved",
            "locus": "",
            "locus_sortable": "",
            "alias_symbol": [],
            "alias_name": [],
            "prev_symbol": [],
            "prev_name": [],
            "date_approved_reserved": None,
            "date_symbol_changed": None,
            "date_name_changed": None,
            "date_modified": None,
            "entrez_id": None,
            "ensembl_gene_id": None,
            "refseq_accession": [],
            "cosmic": [],
            "omim_id": [],
            "pseudogene_org": [],
            "imgt": None,
            "lncrnadb": None,
            "lncipedia": None,
            "ensembl_mane_select": "",
            "refseq_mane_select": "",
            "chromosome": "",
            "other_chromosome": None,
            "start": "",
            "end": "",
            "gene_gc_content": None,
            "gene_description": "",
            "ensembl_canonical": False,
            "gene_type": [],
            "refseq_mane_plus_clinical": [],
            "addtional_transcript_info": {},
            "symbol": cleaned,
            "display_symbol": cleaned,
            "resolved_symbol": cleaned,
            "hgnc_match_source": "unresolved",
            "symbol_changed": False,
        }

    @classmethod
    def _merge_with_placeholders(
        cls, symbols: List[str], rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return one catalog row per requested symbol with HGNC resolution metadata.

        Args:
                symbols: Symbols.
                rows: Rows.

        Returns:
                The  merge with placeholders result.
        """
        by_symbol: dict[str, Dict[str, Any]] = {}
        for row in rows or []:
            for symbol in cls._row_symbols(row):
                by_symbol.setdefault(symbol, row)

        out_rows: List[Dict[str, Any]] = []
        seen_requested: set[str] = set()
        for symbol in symbols or []:
            requested = str(symbol or "").strip()
            if not requested:
                continue
            requested_upper = requested.upper()
            if requested_upper in seen_requested:
                continue
            seen_requested.add(requested_upper)
            resolved = by_symbol.get(requested_upper)
            out_rows.append(
                cls._row_with_requested_symbol(resolved, requested)
                if resolved
                else cls._hgnc_placeholder(requested)
            )

        return sorted(
            out_rows, key=lambda g: (g.get("display_symbol") or g.get("hgnc_symbol") or "").upper()
        )

    def apply_drug_info(
        self, genes: List[Dict[str, Any]], druglist_name: str | None = None
    ) -> List[Dict[str, Any]]:
        """Annotate genes with drug-target membership."""
        drug_genes = self.gene_list_repository.get_isgl(druglist_name) or {}
        drug_symbols = set(drug_genes.get("genes", [])) if drug_genes else set()
        for gene in genes:
            symbol = gene.get("hgnc_symbol") or gene.get("symbol") or ""
            gene["drug_target"] = symbol in drug_symbols
        return genes

    def genelist_view_context(
        self, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any] | None:
        """Return public view context for a genelist."""
        genelist = self.gene_list_repository.get_isgl(genelist_id, is_active=True)
        if not genelist:
            return None

        selected_assay = assay
        all_genes = genelist.get("genes", [])
        asp_ids = genelist.get("asp_ids", [])

        filtered_genes = all_genes
        germline_genes: list[str] = []
        if selected_assay and selected_assay in asp_ids:
            panel = self.assay_panel_repository.get_asp(selected_assay)
            panel_genes = panel.get("covered_genes", []) if panel else []
            germline_genes = panel.get("germline_genes", []) if panel else []
            filtered_genes = (
                sorted(set(all_genes).intersection(panel_genes))
                if panel and panel.get("asp_family") not in ["WGS", "WTS"]
                else all_genes
            )

        return {
            "genelist": genelist,
            "selected_assay": selected_assay,
            "filtered_genes": filtered_genes,
            "germline_genes": germline_genes,
            "is_public": True,
        }

    def asp_genes_payload(self, asp_id: str) -> dict[str, Any]:
        """Return public gene metadata for an assay panel."""
        gene_symbols, germline_gene_symbols = self.assay_panel_repository.get_asp_genes(asp_id)
        gene_details = list(
            self.hgnc_repository.get_metadata_by_symbols(list(gene_symbols or [])) or []
        )
        asp = self.assay_panel_repository.get_asp(asp_id) or {}
        catalog = self._catalog_category_for_asp(asp_id)
        return {
            "asp_id": asp_id,
            "asp": asp,
            "catalog": catalog,
            "stats": {
                "covered_total": len(gene_symbols or []),
                "germline_total": len(germline_gene_symbols or []),
                "displayed_total": len(gene_details),
            },
            "gene_details": gene_details,
            "germline_gene_symbols": list(germline_gene_symbols or []),
        }

    def _catalog_category_for_asp(self, asp_id: str) -> dict[str, Any]:
        """Return the public catalog category metadata for an ASP."""
        catalog = self.load_catalog()
        matches: list[dict[str, Any]] = []
        for modality_key, modality in (catalog.get("modalities") or {}).items():
            for category_key, category in (modality.get("categories") or {}).items():
                if str(category.get("asp_id") or "").strip() != asp_id:
                    continue
                matches.append(
                    {
                        "modality": modality_key,
                        "modality_label": modality.get("label") or modality_key,
                        "category_key": category_key,
                        **category,
                    }
                )
        if not matches:
            return {}
        for match in matches:
            if match.get("catalog_id") == asp_id or match.get("category_key") == asp_id:
                return match
        return matches[0]

    def assay_catalog_gene_symbols_payload(self, isgl_key: str) -> dict[str, Any]:
        """Return gene symbols for a public assay-catalog genelist."""
        isgl = self.gene_list_repository.get_isgl(isgl_key) or {}
        gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()
        return {"gene_symbols": sorted(gene_symbols)}

    def isgl_genes_for_matrix(self, isgl_key: str) -> set[str]:
        """Return active public genelist genes for the assay matrix."""
        isgl_doc = (
            self.gene_list_repository.get_isgl(isgl_key, is_active=True, is_public=True) or {}
        )
        return set(isgl_doc.get("genes") or [])

    def assay_catalog_matrix_payload(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        gene: str | None = None,
    ) -> dict[str, Any]:
        """Return a paged public assay-catalog matrix payload."""
        catalog = self.load_catalog()
        modalities = catalog.get("modalities") or {}
        order = self.modalities_order() or list(modalities.keys())
        page = max(int(page or 1), 1)
        per_page = min(max(int(per_page or 100), 1), 500)
        gene_query = str(gene or "").strip()

        columns: list[dict[str, Any]] = []
        mod_spans: dict[str, int] = {}
        cat_spans: dict[str, int] = {}
        all_genes: set[str] = set()
        column_genes: list[tuple[dict[str, Any], set[str]]] = []

        for mod_key in order:
            mod_data = modalities.get(mod_key) or {}
            categories = mod_data.get("categories") or {}
            modality_total = 0

            for cat_key, cat_data in categories.items():
                asp_id = cat_data.get("asp_id")
                gene_lists = cat_data.get("gene_lists") or []
                real_lists = [gl for gl in gene_lists if gl.get("key")]
                cat_label = cat_data.get("label") or cat_data.get("title") or cat_key
                assay_label = cat_data.get("asp_id") or cat_data.get("catalog_id") or cat_label
                subpanel_label = cat_data.get("subpanel_id") or SUBPANEL_BASE_ID

                if not real_lists:
                    cat_spans[f"{mod_key}::{cat_key}"] = 1
                    modality_total += 1
                    col = {
                        "mod": mod_key,
                        "cat": cat_key,
                        "family": str(cat_data.get("family") or cat_data.get("asp_family") or ""),
                        "assay_group": str(cat_data.get("assay_group") or cat_label),
                        "assay": str(assay_label),
                        "subpanel": str(subpanel_label),
                        "cat_label": str(cat_label),
                        "isgl_key": f"__none__::{mod_key}::{cat_key}",
                        "isgl_label": "-",
                        "placeholder": True,
                    }
                    columns.append(col)
                    column_genes.append((col, set()))
                    continue

                cat_spans[f"{mod_key}::{cat_key}"] = len(real_lists)
                modality_total += len(real_lists)

                for gl in real_lists:
                    isgl_key = gl["key"]
                    isgl_label = gl.get("label") or isgl_key
                    if (asp_id and asp_id == isgl_key) or isgl_key == "single_gene":
                        genes_here = set(self._covered_genes(asp_id)[0])
                    else:
                        genes_here = self.isgl_genes_for_matrix(isgl_key)
                    col = {
                        "mod": mod_key,
                        "cat": cat_key,
                        "family": str(cat_data.get("family") or cat_data.get("asp_family") or ""),
                        "assay_group": str(cat_data.get("assay_group") or cat_label),
                        "assay": str(assay_label),
                        "subpanel": str(subpanel_label),
                        "cat_label": str(cat_label),
                        "isgl_key": isgl_key,
                        "isgl_label": isgl_label,
                        "placeholder": False,
                    }
                    columns.append(col)
                    column_genes.append((col, genes_here))
                    all_genes |= genes_here

            if not categories and modality_total == 0:
                placeholder_key = f"__none__::{mod_key}"
                col = {
                    "mod": mod_key,
                    "cat": "__none__",
                    "family": "",
                    "assay_group": str(mod_data.get("label") or mod_key),
                    "assay": "-",
                    "subpanel": SUBPANEL_BASE_ID,
                    "cat_label": str(mod_data.get("label") or mod_key),
                    "isgl_key": placeholder_key,
                    "isgl_label": "-",
                    "placeholder": True,
                }
                columns.append(col)
                column_genes.append((col, set()))
                mod_spans[mod_key] = 1
                cat_spans[f"{mod_key}::__none__"] = 1
            else:
                mod_spans[mod_key] = modality_total if modality_total > 0 else 1

        sorted_genes = sorted(all_genes)
        if gene_query:
            needle = gene_query.upper()
            filtered_genes = [item for item in sorted_genes if needle in item.upper()]
        else:
            filtered_genes = sorted_genes

        total = len(filtered_genes)
        if gene_query:
            visible_genes = filtered_genes[: min(total, 500)]
            page = 1
            per_page = len(visible_genes) or per_page
        else:
            start = (page - 1) * per_page
            visible_genes = filtered_genes[start : start + per_page]

        matrix: dict[str, dict[str, Any]] = {}
        visible_set = set(visible_genes)
        for col, genes_here in column_genes:
            if col.get("placeholder"):
                continue
            mod_key = col["mod"]
            cat_key = col["cat"]
            isgl_key = col["isgl_key"]
            for gene_symbol in visible_set.intersection(genes_here):
                matrix.setdefault(gene_symbol, {}).setdefault(mod_key, {}).setdefault(cat_key, {})[
                    isgl_key
                ] = True

        for gene_symbol in visible_genes:
            for col in columns:
                matrix.setdefault(gene_symbol, {}).setdefault(col["mod"], {}).setdefault(
                    col["cat"], {}
                ).setdefault(col["isgl_key"], False)

        return {
            "modalities": modalities,
            "order": order,
            "columns": columns,
            "mod_spans": mod_spans,
            "cat_spans": cat_spans,
            "genes": visible_genes,
            "matrix": matrix,
            "page": page,
            "per_page": per_page,
            "total": total,
            "search": gene_query,
            "has_next": (page * per_page) < total if not gene_query else False,
            "has_previous": page > 1 and not gene_query,
        }
