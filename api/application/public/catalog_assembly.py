"""Resolve public catalog overlays against configured assays and gene lists."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from api.application.resources.availability import available_panels
from api.config.constants import ASP_CATEGORY_OPTIONS, SUBPANEL_BASE_ID
from api.contracts.schemas.public_catalog import clean_catalog_html
from api.domain.catalog_hierarchy import resolve_catalog_categories


class PublicCatalogAssemblyMixin:
    """Assemble catalog modalities, categories and editorial overlays."""

    def _load_catalog_document(self) -> dict[str, Any]:
        """Return center-owned presentation metadata from the primary database."""
        if self.public_assay_catalog_repository is None:
            return {}
        document = self.public_assay_catalog_repository.get_default()
        return dict(document) if isinstance(document, dict) else {}

    @staticmethod
    def _overlay_modalities(overlay: dict[str, Any]) -> dict[str, Any]:
        """Extract dictionary-shaped modality presentation metadata.

        Args:
            overlay: Center catalog document.

        Returns:
            Stored modalities mapping, or an empty mapping for other shapes.
        """
        modalities = overlay.get("modalities")
        return modalities if isinstance(modalities, dict) else {}

    @staticmethod
    def _overlay_categories(overlay: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten direct or modality-scoped category presentation entries.

        Args:
            overlay: Catalog with a direct category list or modality categories.

        Returns:
            Dictionary entries in input order. A direct list takes precedence;
            nested entries receive modality/key defaults without overriding stored fields.
        """
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
        """Find the first overlay category matching any supported identity.

        Args:
            overlay: Center presentation metadata to search.
            asp_id: Assay ID for the assay/subpanel match.
            subpanel_id: Subpanel paired with the assay ID.
            aspc_id: Optional explicit configuration ID match.
            catalog_id: Catalog ID or category key to match.

        Returns:
            First matching entry in traversal order, or an empty mapping.
        """
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
        """Find a category's first gene-list presentation override by identifier.

        Args:
            category_overlay: Category containing optional gene_lists.
            isgl_id: Identifier matched against stripped isgl_id or key text.

        Returns:
            Matching dictionary, or an empty mapping when absent.
        """
        for item in category_overlay.get("gene_lists") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("isgl_id") or item.get("key") or "").strip()
            if item_id == isgl_id:
                return item
        return {}

    def load_catalog(self, *, preview_document: dict[str, Any] | None = None) -> Dict[str, Any]:
        """Build the public assay catalog from active ASP, ASPC, and ISGL documents.

        Returns:
            Dict[str, Any]: Catalog data in the UI contract shape.
        """
        active_asps = available_panels(self.assay_panel_repository)
        active_isgls = self.gene_list_repository.get_all_isgl(
            is_active=True, is_public=True, adhoc=False
        )
        overlay = self._load_catalog_document() if preview_document is None else preview_document
        overlay_modalities = self._overlay_modalities(overlay)
        isgls_by_asp = self._group_isgls_by_asp_and_subpanel(active_isgls)
        nav_groups = self._nav_groups_from_asps(active_asps)

        if overlay or preview_document is not None:
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
                or "Catalog generated from center metadata and active collection documents.",
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
                family_key = f"family_{family}"
                group_key = f"{family_key}_{assay_group}"
                categories.setdefault(
                    family_key,
                    {
                        "label": "Panels" if family == "panel" else family.upper(),
                        "node_kind": "folder",
                        "gene_lists": [],
                    },
                )
                categories.setdefault(
                    group_key,
                    {
                        "label": self._title(assay_group),
                        "parent_key": family_key,
                        "node_kind": "folder",
                        "gene_lists": [],
                    },
                )
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
                    categories[category_key]["parent_key"] = group_key
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
                    else f"Explore {category.upper()} assays by family and assay group."
                ),
                "categories": categories,
                "omics": category,
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
            or "Catalog generated from active ASP, ASPC, and public ISGL collection documents with optional center metadata.",
            "layout": {"order": order},
            "modalities": modalities,
            "nav_groups": nav_groups,
        }

    @staticmethod
    def _overlay_order(overlay: dict[str, Any], modalities: dict[str, Any]) -> list[str]:
        """Keep configured modality order and append unlisted available modalities.

        Args:
            overlay: Catalog with optional layout.order list.
            modalities: Available modality mapping.

        Returns:
            Existing configured keys followed by remaining keys in mapping order.
        """
        layout = overlay.get("layout") if isinstance(overlay.get("layout"), dict) else {}
        configured = layout.get("order") if isinstance(layout.get("order"), list) else []
        ordered = [str(item) for item in configured if str(item) in modalities]
        ordered.extend(key for key in modalities if key not in ordered)
        return ordered

    def _nav_groups_from_asps(self, active_asps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group assays into sample-navigation links by category, family, and group.

        Args:
            active_asps: Active assay documents; rows without an assay ID are skipped.

        Returns:
            Sorted group descriptors with assay IDs and sample query fields.
        """
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
        """Resolve configured modality entries against active assay and gene-list data.

        Args:
            overlay_modalities: Presentation modalities with list or mapping categories.
            active_asps: Active assay documents indexed by asp_id.
            active_isgls: Active public gene-list documents indexed by isgl_id.

        Returns:
            Modality payloads in overlay order, with hydrated categories and empty
            sample_groups; non-dictionary modality/category entries are skipped.
        """
        asp_by_id = {str(asp.get("asp_id") or "").strip(): dict(asp) for asp in active_asps or []}
        isgl_by_id = {
            str(isgl.get("isgl_id") or "").strip(): dict(isgl) for isgl in active_isgls or []
        }
        modalities: dict[str, Any] = {}

        for modality_key, modality_overlay in overlay_modalities.items():
            if not isinstance(modality_overlay, dict):
                continue
            categories: dict[str, Any] = {}
            raw_categories = resolve_catalog_categories(modality_overlay)
            category_items = (
                raw_categories.items()
                if isinstance(raw_categories, dict)
                else enumerate(raw_categories or [])
            )
            for raw_key, raw_category in category_items:
                if not isinstance(raw_category, dict):
                    continue
                if str(raw_category.get("asp_id") or "").strip() not in asp_by_id and not (
                    raw_category.get("node_kind") == "folder" and not raw_category.get("asp_id")
                ):
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
        """Merge one configured catalog entry with assay, configuration, and list metadata.

        Args:
            category_key: Mapping key used for missing identity and display labels.
            category_overlay: Center-defined entry and presentation overrides.
            asp_by_id: Active assay documents by ID.
            isgl_by_id: Active public gene-list documents by ID.

        Returns:
            Entry payload retaining overrides and filling assay/reporting details;
            missing assay metadata does not remove the entry.
        """
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
        general_lists = any(not item.get("analysis") for item in gene_lists)
        analysis = category_overlay.get("analysis") or (
            [] if general_lists else self._aspc_available_analysis(aspc)
        )

        payload = {
            **category_overlay,
            "catalog_id": category_overlay.get("catalog_id") or category_key,
            "label": category_overlay.get("label") or category_overlay.get("title") or category_key,
            "title": category_overlay.get("title") or category_overlay.get("label") or category_key,
            "description": clean_catalog_html(
                category_overlay.get("description") or asp.get("description") or ""
            ),
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
        for field in category_overlay.get("clear_fields") or []:
            payload[field] = category_overlay.get(field)
        return payload

    def _overlay_aspc(self, category_overlay: dict[str, Any], asp_id: str) -> dict[str, Any] | None:
        """Resolve the configuration reference selected by an overlay category.

        Args:
            category_overlay: Entry with optional aspc_id or environment-to-ID mapping.
            asp_id: Assay used for first-active-configuration lookup without references.

        Returns:
            Configuration or None. Explicit ID takes precedence over environment
            mapping, which takes precedence over assay lookup; failed lookups do not retry.
        """
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
        """Combine list presentation overrides with public list and category defaults.

        Args:
            item: List entry with optional isgl_id/key and display fields.
            category_overlay: Parent defaults for subpanel and presentation fields.
            isgl_by_id: Public list documents by identifier.

        Returns:
            List payload, or an empty mapping when both identifier and label are absent.
        """
        isgl_id = str(item.get("isgl_id") or item.get("key") or "").strip()
        if not isgl_id and not item.get("label"):
            return {}
        isgl = isgl_by_id.get(isgl_id, {})
        return {
            **item,
            "key": isgl_id,
            "catalog_id": item.get("catalog_id") or isgl_id,
            "label": item.get("label") or isgl.get("displayname") or isgl.get("name") or isgl_id,
            "description": clean_catalog_html(
                item.get("description") or isgl.get("description") or ""
            ),
            "diagnosis": item.get("diagnosis") or isgl.get("diagnosis") or [],
            "subpanel_id": item.get("subpanel_id")
            or isgl.get("subpanel_id")
            or category_overlay.get("subpanel_id")
            or SUBPANEL_BASE_ID,
            "list_type": item.get("list_type") or isgl.get("list_type") or [],
            "tat": item.get("tat") or category_overlay.get("tat"),
            "input_material": item.get("input_material") or category_overlay.get("input_material"),
            "sample_modes": item.get("sample_modes") or category_overlay.get("sample_modes"),
            "analysis": item.get("analysis") or [],
        }
