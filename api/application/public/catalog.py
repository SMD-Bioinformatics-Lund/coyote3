"""Public assay catalog application service used by FastAPI public routes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from api.application.public.catalog_assembly import PublicCatalogAssemblyMixin
from api.application.public.catalog_gene_views import PublicCatalogGeneViewsMixin
from api.config.constants import ASP_CATEGORY_OPTIONS, DEFAULT_ENVIRONMENT, SUBPANEL_BASE_ID
from api.contracts.schemas.public_catalog import clean_catalog_html
from api.domain.common.errors import api_error


class PublicCatalogService(PublicCatalogAssemblyMixin, PublicCatalogGeneViewsMixin):
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
            knowledgebase_version_repository=getattr(
                store, "knowledgebase_version_repository", None
            ),
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
            civic_repository=getattr(store, "civic_repository", None),
            cosmic_repository=getattr(store, "cosmic_repository", None),
            public_assay_catalog_repository=store.public_assay_catalog_repository,
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
        knowledgebase_version_repository: Any | None = None,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
        civic_repository: Any | None = None,
        cosmic_repository: Any | None = None,
        public_assay_catalog_repository: Any | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.hgnc_repository = hgnc_repository
        self.gene_list_repository = gene_list_repository
        self.sample_repository = sample_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.knowledgebase_version_repository = knowledgebase_version_repository
        self.oncokb_public_cache_repository = oncokb_public_cache_repository
        self.clinpgx_public_repository = clinpgx_public_repository
        self.civic_repository = civic_repository
        self.cosmic_repository = cosmic_repository
        self.public_assay_catalog_repository = public_assay_catalog_repository

    def knowledgebase_status(self) -> dict[str, Any]:
        """Return non-sensitive installed knowledgebase release metadata."""
        releases = (
            self.knowledgebase_version_repository.list_active_releases()
            if self.knowledgebase_version_repository is not None
            else []
        )
        return {
            "releases": releases,
            "summary": {
                "installed_products": len(releases),
                "total_records": sum(int(item.get("records") or 0) for item in releases),
            },
        }

    def observed_software_versions(self) -> dict[str, object]:
        """Return bounded software versions observed across ready samples."""
        observed = self.sample_repository.get_observed_software_versions()
        return {"pipelines": observed.get("pipelines") or {}}

    def observed_reference_versions(self) -> dict[str, object]:
        """Return observed sample and configured VEP metadata versions."""
        return {
            "sample_database_versions": self.sample_repository.get_observed_database_versions(),
            "vep_metadata": self.vep_metadata_repository.list_versions(),
        }

    def vep_reference_versions(self) -> dict:
        """Return installed numeric major releases without reading sample data.

        Returns:
            Major-release identifiers sorted newest first.
        """
        versions = self.vep_metadata_repository.list_versions()
        return {"versions": sorted((v for v in versions if v.isdecimal()), key=int, reverse=True)}

    def vep_reference(self, release: str) -> dict:
        """Return one installed public VEP reference without substituting another release.

        Args:
            release: Major release selected by the caller.

        Returns:
            Public reference definitions, provenance and an optional stored diagram.

        Raises:
            APIError: The selected release is not installed.
        """
        document = self.vep_metadata_repository.get_public_reference(release)
        if not document:
            raise api_error(404, "VEP reference release is not installed")
        return document

    def vep_diagram(self, release: str) -> dict:
        """Return a release's binary diagram independently of its reference tables.

        Args:
            release: Exact installed major release.

        Returns:
            Original image bytes, MIME type and content digest.

        Raises:
            APIError: No diagram is installed for this release.
        """
        diagram = self.vep_metadata_repository.get_diagram(release)
        if not diagram:
            raise api_error(404, "VEP diagram is not installed")
        return diagram

    def modalities_order(self) -> List[str]:
        """Return the display order for catalog modalities.

        Returns:
            List[str]: Ordered modality keys.
        """
        catalog = self.load_catalog()
        order = (catalog.get("layout") or {}).get("order") or []
        return order or list((catalog.get("modalities") or {}).keys())

    def normalize_mod(
        self, mod: Optional[str], *, catalog: dict[str, Any] | None = None
    ) -> Optional[str]:
        """Normalize modality aliases to catalog keys.

        Args:
            mod: Raw modality value from the request.

        Returns:
            Optional[str]: Canonical modality key when recognized.
        """
        if not mod:
            return None
        catalog_modalities = (self.load_catalog() if catalog is None else catalog).get(
            "modalities"
        ) or {}
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

    def modality_block(
        self, mod: str, *, catalog: dict[str, Any] | None = None
    ) -> Optional[Dict[str, Any]]:
        """Return the catalog block for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Optional[Dict[str, Any]]: Catalog block for the modality.
        """
        return ((self.load_catalog() if catalog is None else catalog).get("modalities") or {}).get(
            mod
        )

    def categories_for(
        self, mod: str, *, catalog: dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        """Return category entries for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            List[Dict[str, Any]]: Category descriptors for the modality.
        """
        modality = self.modality_block(mod, catalog=catalog) or {}
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

    def category_def(
        self, mod: str, cat_id: str, *, catalog: dict[str, Any] | None = None
    ) -> Optional[Dict[str, Any]]:
        """Return the catalog definition for a modality category.

        Args:
            mod: Canonical modality key.
            cat_id: Category identifier to resolve.

        Returns:
            Optional[Dict[str, Any]]: Category definition when found.
        """
        modality = self.modality_block(mod, catalog=catalog) or {}
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
        """Turn a machine label into title-cased words.

        Args:
            value: Label to stringify; falsey values become empty text.

        Returns:
            Title-cased text with underscores and hyphens replaced by spaces.
        """
        return str(value or "").replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _family_bucket(asp: dict[str, Any]) -> str:
        """Collapse panel-prefixed assay families into a shared navigation bucket.

        Args:
            asp: Assay document with optional asp_family.

        Returns:
            Stripped lowercase family, panel for panel prefixes, or assay when blank.
        """
        family = str(asp.get("asp_family") or "").strip().lower()
        if family.startswith("panel"):
            return "panel"
        return family or "assay"

    @staticmethod
    def _aspc_subpanel_id(aspc: dict[str, Any] | None) -> str:
        """Read a nonblank configuration subpanel with the base ID as default.

        Args:
            aspc: Configuration document, or None.

        Returns:
            Stripped subpanel ID or SUBPANEL_BASE_ID.
        """
        return str((aspc or {}).get("subpanel_id") or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID

    @staticmethod
    def _aspc_catalog(aspc: dict[str, Any] | None) -> dict[str, Any]:
        """Extract dictionary-shaped catalog settings from a configuration.

        Args:
            aspc: Configuration document, or None.

        Returns:
            Stored catalog mapping, or an empty mapping when absent or malformed.
        """
        catalog = (aspc or {}).get("catalog")
        return catalog if isinstance(catalog, dict) else {}

    @classmethod
    def _category_key(cls, asp: dict[str, Any], aspc: dict[str, Any] | None = None) -> str:
        """Compose catalog identity from assay family, group, ID, and subpanel.

        Args:
            asp: Assay identity and grouping fields.
            aspc: Optional configuration supplying the subpanel; None uses base.

        Returns:
            Four components joined by double colons, with unassigned for a blank group.
        """
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
        """Stringify and deduplicate nonblank values without changing their order.

        Args:
            values: Values converted to stripped strings, including None as literal text.

        Returns:
            Distinct nonempty strings in first-occurrence order.
        """
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    @classmethod
    def _aspc_available_analysis(cls, aspc: dict[str, Any] | None) -> list[str]:
        """Read distinct nonblank analysis types from a configuration.

        Args:
            aspc: Configuration with optional analysis_types; None yields no types.

        Returns:
            Stripped analysis names in stored order without case normalization.
        """
        if not aspc:
            return []
        return cls._unique(list(aspc.get("analysis_types") or []))

    @classmethod
    def _aspc_report_sections(cls, aspc: dict[str, Any] | None) -> list[str]:
        """Read distinct reporting section names from dictionary-shaped settings.

        Args:
            aspc: Configuration with optional reporting settings; None yields no sections.

        Returns:
            Nonblank stripped names in stored order without case normalization.
        """
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
        """Build a collection-derived category with optional center presentation overrides.

        Args:
            asp: Active assay supplying identity, platform, and default labels.
            aspc: Optional configuration supplying subpanel and reporting analyses.
            family: Navigation family bucket.
            assay_group: Navigation assay group.
            gene_lists: Public lists selected for this assay/subpanel.
            overlay: Optional center metadata used to locate category and list overrides.

        Returns:
            Category with an all-covered-genes entry followed by named list entries.
        """
        asp_id = str(asp.get("asp_id") or "")
        subpanel_id = self._aspc_subpanel_id(aspc)
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
            or aspc_display_name
            or asp.get("display_name")
            or asp.get("asp_id")
            or asp_id
        )
        if subpanel_id != SUBPANEL_BASE_ID and not (
            category_overlay.get("title") or category_overlay.get("label")
        ):
            display_name = f"{display_name} - {self._title(subpanel_id)}"
        analyses = category_overlay.get("analysis") or self._aspc_available_analysis(aspc)
        list_entries = [
            {
                "key": asp_id,
                "catalog_id": asp_id,
                "label": category_overlay.get("covered_genes_label") or "All covered genes",
                "description": clean_catalog_html(
                    category_overlay.get("covered_genes_description")
                    or f"All genes targeted by {display_name}."
                ),
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
                    "description": clean_catalog_html(
                        list_overlay.get("description") or isgl.get("description") or ""
                    ),
                    "diagnosis": isgl.get("diagnosis") or [],
                    "subpanel_id": subpanel_id,
                    "list_type": isgl.get("list_type") or [],
                    "tat": list_overlay.get("tat") or category_overlay.get("tat"),
                    "input_material": list_overlay.get("input_material")
                    or category_overlay.get("input_material"),
                    "sample_modes": list_overlay.get("sample_modes")
                    or category_overlay.get("sample_modes"),
                    "analysis": list_overlay.get("analysis")
                    or [
                        analysis
                        for analysis in analyses
                        if analysis.lower() in (isgl.get("list_type") or [])
                    ],
                }
            )
        return {
            "catalog_id": catalog_id,
            "label": display_name,
            "title": display_name,
            "description": clean_catalog_html(
                category_overlay.get("description")
                or (aspc or {}).get("description")
                or asp.get("description")
                or ""
            ),
            "subheading": category_overlay.get("subheading"),
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
            "input_material": category_overlay.get("input_material") or asp.get("asp_category"),
            "tat": category_overlay.get("tat"),
            "sample_modes": category_overlay.get("sample_modes") or ["paired", "single"],
            "analysis": analyses,
            "no_gene_list": [
                analysis
                for analysis in analyses
                if not any(analysis in (item.get("analysis") or []) for item in list_entries)
            ],
            "report_sections": self._aspc_report_sections(aspc),
            "clinical_indications": category_overlay.get("clinical_indications") or [],
            "limitations": category_overlay.get("limitations"),
            "public_notes": category_overlay.get("public_notes"),
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
        """Index public lists under every associated assay and diagnosis subpanel.

        Args:
            isgls: List documents with asp_ids and diagnosis IDs; absent diagnoses use base.

        Returns:
            Assay/subpanel mappings of shallow document copies sorted by display name,
            name, or identifier.
        """
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for isgl in isgls or []:
            diagnosis_ids = [
                str(value).strip() for value in (isgl.get("diagnosis") or []) if str(value).strip()
            ] or [SUBPANEL_BASE_ID]
            for asp_id in isgl.get("asp_ids") or []:
                key = str(asp_id or "").strip()
                if key:
                    for diagnosis_id in diagnosis_ids:
                        grouped.setdefault(key, {}).setdefault(diagnosis_id, []).append(dict(isgl))
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
        """Select subpanel lists followed by base lists, keeping each list ID once.

        Args:
            isgls_by_subpanel: Lists grouped under diagnosis/base subpanel IDs.
            subpanel_id: Requested subpanel; base does not append itself twice.

        Returns:
            First document for each nonblank isgl_id in selection order.
        """
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
        self,
        mod: str,
        cat_id: str,
        gl_id: str | None = None,
        env: str = DEFAULT_ENV,
        *,
        catalog: dict[str, Any] | None = None,
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
        node = self.category_def(mod, cat_id, catalog=catalog)
        if not node:
            return None

        asp_id = node.get("asp_id")
        aspc_id = node.get("aspc_id")
        aspc_ids = node.get("aspc_ids") or {}

        aspc = self.assay_configuration_repository.get_aspc_with_id(aspc_id) if aspc_id else None
        if not aspc and aspc_ids:
            aspc = self._fetch_aspc(aspc_ids, env)

        analysis = node.get("analysis", []) or []
        if (
            aspc
            and not analysis
            and "analysis" not in (node.get("clear_fields") or [])
            and not any(not item.get("analysis") for item in node.get("gene_lists") or [])
        ):
            analysis = self._aspc_available_analysis(aspc)

        return {
            "catalog_id": node.get("catalog_id") or cat_id,
            "label": node.get("label", cat_id),
            "title": node.get("title", node.get("label", cat_id)),
            "description": node.get("description", ""),
            "subheading": node.get("subheading"),
            "input_material": node.get("input_material"),
            "tat": node.get("tat"),
            "sample_modes": node.get("sample_modes", []),
            "analysis": analysis,
            "no_gene_list": node.get("no_gene_list") or [],
            "report_sections": node.get("report_sections")
            if "report_sections" in (node.get("clear_fields") or [])
            else node.get("report_sections") or self._aspc_report_sections(aspc),
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

    def hydrate_modality(
        self, mod: str, *, catalog: dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Hydrate summary metadata for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Dict[str, Any]: Hydrated modality payload.
        """
        modality = self.modality_block(mod, catalog=catalog) or {}
        return {
            "title": modality.get("title") or modality.get("label", mod),
            "label": modality.get("label", mod),
            "description": modality.get("description", ""),
            "input_material": modality.get("input_material"),
            "tat": modality.get("tat"),
            "sample_modes": modality.get("sample_modes", []),
            "analysis": modality.get("analysis", []),
            "report_sections": modality.get("report_sections", []),
            "clinical_indications": modality.get("clinical_indications", []),
            "limitations": modality.get("limitations"),
            "public_notes": modality.get("public_notes"),
            "asp_id": modality.get("asp_id"),
            "asp": modality.get("asp"),
            "gene_lists": [
                {**item, "key": item.get("key") or item.get("isgl_id")}
                for item in modality.get("gene_lists") or []
            ],
        }

    def catalog_context(
        self,
        mod: str | None = None,
        cat: str | None = None,
        isgl_key: str | None = None,
        *,
        preview_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build public and draft views, returning an empty landing context before setup.

        Args:
            mod: Optional modality identifier to open.
            cat: Optional category within the selected modality.
            isgl_key: Optional gene-list selection.
            preview_document: Unpublished document for an authorized draft preview.

        Returns:
            Catalog context; an empty order represents no configured catalog entries.

        Raises:
            AppError: A requested entry is unavailable.
        """
        catalog = self.load_catalog(preview_document=preview_document)
        order = (catalog.get("layout") or {}).get("order") or list(catalog.get("modalities") or {})
        if not order and (mod or cat or isgl_key):
            raise api_error(404, "Catalog not found")

        selected_mod = self.normalize_mod(mod, catalog=catalog) if mod else None
        selected_cat = cat if cat else None
        selected_isgl = isgl_key if isgl_key else None
        mods = catalog.get("modalities") or {}

        if not selected_mod:
            right = {
                "title": catalog.get("header") or "Assay Catalog",
                "description": catalog.get("description")
                or "Select a modality to explore available assays.",
                "input_material": None,
                "tat": None,
                "sample_modes": [],
                "analysis": [],
                "report_sections": [],
                "asp_id": None,
                "aspc_id": None,
                "aspc_ids": {},
                "subpanel_id": None,
                "asp": None,
                "clinical_indications": [],
                "limitations": None,
                "public_notes": None,
                "gene_lists": [],
            }
            gene_mode, genes, stats = (
                "covered",
                [],
                {"total": 0, "covered_total": 0, "germline_total": 0},
            )
        elif selected_mod and not selected_cat:
            right = self.hydrate_modality(selected_mod, catalog=catalog)
            gene_mode, genes, stats = self.resolve_gene_table(right.get("asp_id"), selected_isgl)
        else:
            if selected_isgl:
                hydrated_cat = self.hydrate_category(
                    selected_mod,
                    selected_cat,
                    selected_isgl,
                    env=DEFAULT_ENVIRONMENT,
                    catalog=catalog,
                )
            else:
                hydrated_cat = self.hydrate_category(
                    selected_mod, selected_cat, env=DEFAULT_ENVIRONMENT, catalog=catalog
                )
            if not hydrated_cat:
                raise api_error(404, "Category not found")
            right = {
                "title": hydrated_cat.get("title") or hydrated_cat.get("label"),
                "catalog_id": hydrated_cat.get("catalog_id"),
                "subheading": hydrated_cat.get("subheading"),
                "description": hydrated_cat.get("description"),
                "input_material": hydrated_cat.get("input_material"),
                "tat": hydrated_cat.get("tat"),
                "sample_modes": hydrated_cat.get("sample_modes") or [],
                "analysis": hydrated_cat.get("analysis") or [],
                "no_gene_list": hydrated_cat.get("no_gene_list") or [],
                "report_sections": hydrated_cat.get("report_sections") or [],
                "asp_id": hydrated_cat.get("asp_id"),
                "aspc_id": hydrated_cat.get("aspc_id"),
                "aspc_ids": hydrated_cat.get("aspc_ids") or {},
                "subpanel_id": hydrated_cat.get("subpanel_id"),
                "asp": hydrated_cat.get("asp"),
                "clinical_indications": hydrated_cat.get("clinical_indications") or [],
                "limitations": hydrated_cat.get("limitations"),
                "public_notes": hydrated_cat.get("public_notes"),
                "gene_lists": hydrated_cat.get("gene_lists") or [],
                "sample_query": hydrated_cat.get("sample_query"),
            }
            gene_mode, genes, stats = self.resolve_gene_table(
                hydrated_cat.get("asp_id"), selected_isgl
            )

        if genes:
            genes = self.apply_drug_info(genes=deepcopy(genes), druglist_name="drug_addon")
            genes = self.apply_knowledgebase_gene_markers(genes)
        vm = {
            "meta": {
                "version": catalog.get("version"),
                "last_updated": catalog.get("last_updated"),
                "maintainer": catalog.get("maintainer"),
                "header": catalog.get("header"),
                "description": catalog.get("description"),
                "nav_groups": catalog.get("nav_groups") or [],
            },
            "order": order,
            "modalities": mods,
            "selected_mod": selected_mod,
            "categories": self.categories_for(selected_mod, catalog=catalog)
            if selected_mod
            else [],
            "selected_cat": selected_cat,
            "selected_isgl": selected_isgl,
            "right": right,
            "gene_mode": gene_mode,
            "genes": genes,
            "stats": stats,
        }
        return vm
