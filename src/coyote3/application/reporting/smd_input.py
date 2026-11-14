"""Project evaluated Coyote3 report facts into the smd-reports JSON contract.

Finding eligibility, transcript selection and clinical wording are resolved before
this boundary. This module supplies presentation values, never database lookups.
"""

import math
from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote
from xml.etree import ElementTree

from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from coyote3.application.reporting.ordering import analysis_priority, order_summary_tables
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.domain.common.reporting import TIER_DESC, TIER_SHORT_DESC
from coyote3.version import __version__


def _value(value: Any) -> Any:
    """Return a JSON cell, preserving missing values, zero and false."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_value(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(str(_value(item)) for item in value)
    return str(value)


def _table(key: str, heading: str, columns: list[str], rows: list[list[Any]], **extra: Any) -> dict:
    """Build a rectangular Swedish table from explicitly selected display fields."""
    return {
        "key": key,
        "kind": "table",
        "heading": heading,
        "columns": {"sv": columns},
        "rows": [[_value(value) for value in row] for row in rows],
        **extra,
    }


def _hgvs(value: Any) -> Any:
    """Decode stored percent-encoded notation without replacing an unavailable value."""
    return unquote(value) if isinstance(value, str) else _value(value)


def _detail(key: str, title: str, fields: list[tuple[str, Any]]) -> dict:
    """Build one finding card without flattening its labels or exposing private fields."""
    fields = [(label, value) for label, value in fields if label != "Kommentar" or value]
    result = _table(key, "", [label for label, _ in fields], [[value for _, value in fields]])
    result.update(kind="details", record_titles=[title], fields_per_row=3)
    result["column_options"] = {
        str(index): {"format": "markdown", "full_width": True}
        for index, (label, _) in enumerate(fields)
        if label == "Kommentar"
    }
    return result


def _comment(row: dict, *, selected: bool = False) -> str:
    """Use the already selected assay annotation, otherwise the latest visible annotation."""
    annotations = row.get("global_annotations") or []
    if not annotations:
        return ""
    preferred = (row.get("annotations_interesting") or {}) if selected else {}
    if preferred:
        return "\n\n".join(str(item.get("text") or "") for item in preferred.values())
    return str(max(annotations, key=lambda item: item.get("time_created") or "").get("text") or "")


def _annotation(row: dict) -> dict:
    """Read the selected structural annotation, then MANE or the first annotation."""
    info = row.get("INFO") or {}
    annotations = info.get("ANN") or []
    selected = next((item for item in annotations if item.get("selected") == 1), None)
    return selected or info.get("MANE_ANN") or next(iter(annotations), {})


def _read_support(value: Any) -> str:
    """Preserve stored read-support text or format reference/alternate counts with slashes."""
    if isinstance(value, str):
        return value
    return "/".join(map(str, value)) if value is not None else "-"


class _CompactSummaryHeadings(Treeprocessor):
    """Format parsed Markdown headings without changing authored words or other blocks."""

    def run(self, root: ElementTree.Element) -> None:
        """Replace headings in the Markdown tree with body-sized bold paragraphs.

        Args:
            root: Parsed Markdown tree, modified before serialization and sanitization.
        """
        for parent in list(root.iter()):
            children = list(parent)
            for index, heading in enumerate(children):
                if heading.tag not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    continue
                heading.tag = "strong"
                heading.attrib.clear()
                following = children[index + 1] if index + 1 < len(children) else None
                position = list(parent).index(heading)
                parent.remove(heading)
                if following is not None and following.tag == "p":
                    line_break = ElementTree.Element("br")
                    line_break.tail = following.text
                    following.text = None
                    heading.tail = None
                    following.insert(0, heading)
                    following.insert(1, line_break)
                else:
                    paragraph = ElementTree.Element("p")
                    paragraph.tail = heading.tail
                    heading.tail = None
                    paragraph.append(heading)
                    parent.insert(position, paragraph)


def _summary_text(context: dict) -> str:
    """Keep reviewed summary words while displaying headings as compact bold paragraphs."""
    text = "\n\n".join(
        value
        for value in (context.get("report_scope_label"), context.get("latest_sample_comment_text"))
        if value
    )
    processor = Markdown(extensions=["extra", "nl2br"], output_format="xhtml")
    processor.preprocessors.deregister("html_block")
    processor.inlinePatterns.deregister("html")
    processor.treeprocessors.register(_CompactSummaryHeadings(processor), "summary_headings", 15)
    return processor.convert(text)


def _summary_copy_number(ratio: Any) -> str:
    """Match master's copy-number rounding while retaining unavailable/invalid values."""
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio):
        return "-"
    try:
        return str(2 * round(2**ratio, 2))
    except OverflowError:
        return "-"


def _metadata(context: dict, analyte: str) -> dict:
    """Retain report identity and patient placeholders without accessing patient records."""
    sample = context["sample"]
    reporting = context["assay_config"].get("reporting") or {}
    number = sample.get("report_num", 0) + 1
    if analyte == "dna":
        identifier = f"{sample.get('case_id', 'NONE')}_{(sample.get('case') or {}).get('clarity_id', 'NONE')}"
        if sample.get("control_id"):
            identifier += (
                f"-{sample['control_id']}_{(sample.get('control') or {}).get('clarity_id', 'NONE')}"
            )
        identifier += f".{context.get('report_timestamp', number)}"
    else:
        identifier = f"{sample.get('name', 'Unknown')}.{number}"
    generated = context.get("report_generated_at")
    if isinstance(generated, str):
        generated = datetime.fromisoformat(generated)
    if generated is None:
        generated = datetime.now().astimezone()
    if generated.tzinfo is None:
        raise ValueError("Report generation time must include a timezone")
    fields = [
        ("Patientnamn", "<PATIENT_NAME>"),
        ("Personnummer", "<PERSONAL_IDENTITY_NUMBER>"),
    ]
    if analyte == "dna" and sample.get("case_id") and sample.get("name"):
        fields.append(("Analys-ID", sample["name"]))
    if analyte == "dna" and sample.get("sample_no") == 2:
        fields.append(("KontrollProv-ID", sample.get("control_id")))
    fields.extend(
        [
            ("Registreringsdatum", "<REGISTRATION_DATE>"),
            ("Provtyp", "<TUMOR_SAMPLE_TYPE>" if analyte == "dna" else "<SAMPLE_TYPE> / RNA"),
        ]
    )
    if context.get("clinical_question"):
        fields.append(("Frågeställning", context["clinical_question"]))
    fields.extend(
        [
            ("Analysmetod", reporting.get("report_method")),
        ]
    )
    branding = context.get("branding") or {}
    laboratory = " och ".join(
        str(value)
        for value in (
            branding.get("center_name") or context.get("organization_name"),
            branding.get("center_department"),
        )
        if value
    )
    if laboratory:
        fields.append(("Analys genomförd av", laboratory))
    fields.extend(
        [
            ("Rapportnummer", number),
        ]
    )
    return {
        "report_id": identifier,
        "sample_id": str(
            (sample.get("case_id") if analyte == "dna" else sample.get("name"))
            or sample.get("name")
            or ""
        ),
        "generated_at": generated.isoformat(),
        "author": context.get("generated_by") or "Unknown",
        "author_label": "Rapport genererad av",
        "fields": [{"label": label, "value": _value(value)} for label, value in fields],
    }


def build_smd_report_input(
    context: dict[str, Any],
    *,
    analyte: str,
    preview: bool,
    presentation: ReportPresentation,
) -> dict[str, Any]:
    """Build the complete JSON-compatible document consumed by ReportLoader.loads.

    Args:
        context: Prepared report context including evaluated narrative and selected findings.
        analyte: DNA or RNA modality, expressed as dna or rna.
        preview: Include an explicit unsaved-report notice when true.
        presentation: Reviewed empty-result wording for each enabled analysis.

    Returns:
        A fresh smd-reports document with ordered metadata, results and detail sections.

    Raises:
        ValueError: The modality or generation timestamp is invalid.
    """
    from coyote3.application.reporting.report_renderer import (
        _copy_number,
        _format_classification,
        _format_tier,
        _perc_no_dec,
    )

    if analyte not in {"dna", "rna"}:
        raise ValueError("Report input requires a DNA or RNA analyte")
    sample = context["sample"]
    config = context["assay_config"]
    data = context.get("report_sections_data") or {}
    enabled = context.get("report_sections") or []
    empty = presentation.empty_results.model_dump()
    short = context.get("class_desc_short") or TIER_SHORT_DESC
    sections: list[dict] = []
    details: list[dict] = []
    if preview:
        sections.append({"key": "preview", "kind": "text", "text": "PREVIEW · UNSAVED REPORT"})
    sections.append({"key": "results", "kind": "text", "heading": "Analysresultat", "text": ""})

    def add_table(key, heading, columns, rows, empty_key):
        """Keep configured empty-result wording alongside enabled result tables."""
        sections.append(_table(key, heading, columns, rows, empty_text=empty[empty_key]))

    if analyte == "dna":
        if "SNV" in enabled:
            for key, heading, empty_key in [
                ("snvs", "Kliniskt relevanta SNVs och små INDELs", "SNV"),
                (
                    "germline_snvs",
                    "Kliniskt relevanta germline-SNVs och små INDELs",
                    "GERMLINE_SNV",
                ),
            ]:
                if key == "germline_snvs" and data.get(key) is None:
                    continue
                rows = data.get(key) or []
                add_table(
                    key,
                    heading,
                    ["Gen", "Mutation", "Variantfrekvens", "Klassificering"],
                    [
                        [
                            row.get("symbol"),
                            row.get("cdna")
                            if (row.get("indel_size") or 0) > 20
                            else _hgvs(row.get("variant")),
                            _perc_no_dec(row.get("af")),
                            row.get("class_short_desc")
                            if row.get("class") in (1, 2, 3, 4)
                            else "-",
                        ]
                        for row in rows
                    ],
                    empty_key,
                )
                sections[-1]["cell_options"] = {
                    str(index): {"3": {"font_weight": "semibold"}}
                    for index, row in enumerate(rows)
                    if row.get("class") == 1
                }
                # Existing detailed cards belong to the somatic result section only.
                if key != "snvs":
                    continue
                for index, row in enumerate(rows):
                    protein = "\n".join(
                        str(value)
                        for value in (row.get("protein_changes") or [row.get("variant")])
                        if value is not None
                    )
                    feature = str(row.get("feature") or "")
                    if row.get("exon"):
                        feature += f", exon {row['exon'][0]}"
                    elif row.get("intron"):
                        feature += f", intron {row['intron'][0]}"
                    name = str(_hgvs(row.get("variant")) or "")
                    if len(name) >= 30:
                        name = row.get("cdna") or ""
                    details.append(
                        _detail(
                            f"snv-{index}",
                            f"{row.get('symbol', '')}: {name or row.get('cdna', '')}",
                            [
                                ("Gen", row.get("symbol")),
                                (
                                    "Typ",
                                    f"{row.get('class_type', '')} {row.get('variant_class', '')}",
                                ),
                                ("Transkript", feature),
                                ("Konsekvens", row.get("consequence")),
                                (
                                    "cDNA-förändring",
                                    _hgvs(row.get("cdna"))
                                    if row.get("var_type") == "snv"
                                    else row.get("cdna"),
                                ),
                                (
                                    "Proteinförändring",
                                    protein
                                    if (row.get("indel_size") or 0) < 20
                                    else row.get("cdna"),
                                ),
                                ("Kromosom", f"chr{row.get('chr', '')}"),
                                ("Position (hg38)", row.get("pos")),
                                ("Frekvens", _perc_no_dec(row.get("af"))),
                                ("Exon", "/".join(row.get("exon") or []) or "-"),
                                ("Intron", "/".join(row.get("intron") or []) or "-"),
                                (
                                    "Klassificering",
                                    _format_classification(
                                        row.get("class"), row.get("class_long_desc")
                                    ),
                                ),
                                ("Kommentar", _comment(row, selected=True)),
                            ],
                        )
                    )
        sections.append(
            {"key": "notation", "kind": "text", "text": "Note: p = protein, c = cDNA, g = genomic"}
        )
        if "CNV" in enabled:
            cnvs = data.get("cnvs") or []
            rows = []
            for index, row in enumerate(cnvs):
                genes = row.get("genes") or []
                selected = [gene.get("gene", "") for gene in genes if gene.get("class")]
                other = len(genes) - len(selected)
                label = " ".join(selected) + (f" + {other} other genes" if other else "")
                tier = (row.get("classification") or {}).get("class")
                ratio = row.get("ratio")
                rows.append(
                    [
                        label.strip(),
                        f"{row.get('size', '-')} bp",
                        ("AMP" if ratio > 1 else "DUP" if ratio > 0 else "DEL")
                        if isinstance(ratio, (int, float))
                        and not isinstance(ratio, bool)
                        and math.isfinite(ratio)
                        else "-",
                        _summary_copy_number(ratio),
                    ]
                )
                details.append(
                    _detail(
                        f"cnv-{index}",
                        ", ".join(gene.get("gene", "") for gene in genes),
                        [
                            ("Kromosom", row.get("chr")),
                            ("Region", f"{row.get('start', '-')}-{row.get('end', '-')}"),
                            ("Storlek", f"{row.get('size', '-')} bp"),
                            ("Typ", row.get("type")),
                            ("Kopietal", _copy_number(row.get("ratio"))),
                            ("Prober", row.get("nprobes")),
                            ("Paired reads (PR)", row.get("PR")),
                            ("Split reads (SR)", row.get("SR")),
                            ("Klassificering", _format_classification(tier, short.get(tier))),
                            ("Kommentar", _comment(row)),
                        ],
                    )
                )
            add_table(
                "cnvs",
                "Kliniskt relevanta genspecifika kopietalsförändringar",
                ["Gen(er)", "Storlek", "Typ", "Kopietal"],
                rows,
                "CNV",
            )
        if "TRANSLOCATION" in enabled or "FUSION" in enabled:
            rows = []
            for index, row in enumerate(data.get("translocs", data.get("fusions")) or []):
                ann = _annotation(row)
                tier = (row.get("classification") or {}).get("class")
                title = (ann.get("Gene_Name") or "-").replace("&", "::")
                exon = ann.get("Rank") or ann.get("EXON") or "-"
                rows.append(
                    [
                        title,
                        _hgvs(ann.get("HGVSp")),
                    ]
                )
                fields = [
                    ("Position", f"{row.get('CHROM', '')}:{row.get('POS', '')}"),
                    ("Allele", row.get("ALT")),
                    ("Exon", exon),
                ]
                for genotype in row.get("GT") or []:
                    fields.extend(
                        [
                            ("Prov", genotype.get("type") or genotype.get("sample")),
                            ("Paired reads (PR)", _read_support(genotype.get("PR"))),
                            ("Split reads (SR)", _read_support(genotype.get("SR"))),
                        ]
                    )
                fields.extend(
                    [
                        ("Klassificering", _format_classification(tier, short.get(tier))),
                        ("Kommentar", _comment(row)),
                    ]
                )
                details.append(_detail(f"translocation-{index}", title, fields))
            add_table(
                "translocations",
                "Kliniskt relevanta fusioner",
                ["Gener", "HGVS.p"],
                rows,
                "TRANSLOCATION",
            )
    else:
        rows = []
        for index, row in enumerate(
            sorted(
                context.get("fusions") or [],
                key=lambda item: (item.get("classification") or {}).get("class", 999),
            )
        ):
            calls = row.get("report_selected_calls") or []
            if not calls:
                raise ValueError("Report fusion requires its selected call")
            call = calls[0]
            tier = (row.get("classification") or {}).get("class")
            title = f"{row.get('gene1', '')}::{row.get('gene2', '')}"
            locus = f"{call.get('breakpoint1', '-')} | {call.get('breakpoint2', '-')}"
            rows.append(
                [
                    f"{row.get('gene1', '')} - {row.get('gene2', '')}",
                    short.get(tier, "-") if tier in (1, 2, 3, 4) else "-",
                ]
            )
            supported = int(call.get("spanpairs") or 0) > 0
            details.append(
                _detail(
                    f"fusion-{index}",
                    title,
                    [
                        ("Gener", title),
                        ("Effekt", (call.get("effect") or "-") if supported else "NA"),
                        ("Fusionspunkter", locus if supported else "NA"),
                        ("Antal läsningar", call.get("spanreads")),
                        ("Antal läs-par", call.get("spanpairs")),
                        (
                            "Längsta ankarsekvens",
                            f"{call['longestanchor']} bp" if call.get("longestanchor") else "NA",
                        ),
                        (
                            "Klassificering",
                            _format_classification(
                                tier, (context.get("class_desc") or TIER_DESC).get(tier)
                            ),
                        ),
                        ("Kommentar", _comment(row)),
                    ],
                )
            )
        add_table(
            "fusions",
            "Kliniskt relevanta fusioner",
            [
                "Fusion/exon skipping" if sample.get("asp_id") == "fusionrna" else "Fusion",
                "Klassificering",
            ],
            rows,
            "FUSION",
        )

    biomarker_analyses = _biomarkers(context, sections, details, empty)
    if "PGX" in enabled:
        pgx = (data.get("pgx") if analyte == "dna" else context.get("pgx")) or []
        add_table(
            "pgx",
            "Farmakogenomiska resultat",
            ["Gen", "Resultat"],
            [
                [
                    row.get("gene") or row.get("symbol") or row.get("hugo_symbol"),
                    next(
                        (
                            row[key]
                            for key in ("result", "phenotype", "diplotype", "records")
                            if row.get(key) is not None and row[key] != ""
                        ),
                        None,
                    ),
                ]
                for row in pgx
            ],
            "PGX",
        )
    order_summary_tables(
        sections,
        (config.get("reporting") or {}).get("summary_table_order") or [],
        biomarker_analyses,
    )
    sections.append(
        {
            "key": "conclusion",
            "kind": "summary",
            "heading": (
                f"Slutsats – {context['clinical_question']}"
                if context.get("clinical_question")
                else "Slutsats"
            ),
            "text": _summary_text(context),
            "format": "markdown",
        }
    )
    if data.get("cnv_profile_base64"):
        sections.append(
            {
                "key": "cnv-profile",
                "kind": "image",
                "heading": "Kopietalsprofil, genomisk översikt",
                "source": "data:image/png;base64," + data["cnv_profile_base64"],
                "page_break_before": True,
            }
        )
    if details:
        details[0]["page_break_before"] = True
        details[0]["heading"] = (
            "Detekterade mutationer" if analyte == "dna" else "Detekterade fusioner"
        )
        sections.extend(details)
    sections.append(
        {
            "key": "description",
            "kind": "description",
            "heading": "Analysbeskrivning",
            "page_break_before": not bool(details),
            "text": {"sv": context.get("analysis_description") or ""},
            "format": "markdown",
        }
    )
    table_number = 1
    for index, (name, genes) in enumerate((context.get("genes_covered_in_panel") or {}).items()):
        if name != sample.get("asp_id"):
            covered = genes.get("covered") or []
            sections.append(
                {
                    "key": f"gene-list-{index}",
                    "kind": "compact_table",
                    "caption": (
                        f"Tabell {table_number}: Gener inkluderade i {name} insilico-panel"
                    ),
                    "items": list(covered),
                    "columns": 15,
                }
            )
            table_number += 1
    branding = context.get("branding") or {}
    public_url = branding.get("public_base_url")
    assay_id = sample.get("asp_id")
    if analyte == "dna" and public_url and assay_id:
        lines = [
            "För analysens genlista, se:",
            f"{public_url}/public/asp/{quote(str(assay_id), safe='')}/genes",
        ]
        applied = {
            name: genes
            for name, genes in (context.get("genes_covered_in_panel") or {}).items()
            if name != assay_id
        }
        if applied:
            lines.extend(["", "För de in silico-genlistor som tillämpats i denna rapport, se:"])
            for name, genes in applied.items():
                if genes.get("adhoc"):
                    lines.append(f"{name}: provspecifik genlista (ingen publik URL).")
                else:
                    lines.append(
                        f"{name}: {public_url}/public/genelists/{quote(str(name), safe='')}/view"
                        f"?assay={quote(str(assay_id), safe='')}"
                    )
        sections.append(
            {
                "key": "panel-reference",
                "kind": "description",
                "heading": "",
                "text": {"sv": "\n".join(lines)},
            }
        )
    if not context.get("germline") or analyte == "rna":
        legend = {
            1: "Variant av stark klinisk signifikans (genmutationer som är diagnostiska, behandlingsstyrande eller riskstratifierande enligt gällande riktlinjer)",
            2: "Variant av potentiell klinisk signifikans (mutationer i gener beskrivna i ett flertal publikationer)",
            3: "Variant av oklar klinisk signifikans (mutationer i gener beskrivna i ett fåtal publikationer)",
            4: "Variant bedömd som benign eller sannolikt benign",
        }
        if analyte == "rna":
            legend.update(
                {
                    1: "Variant av stark klinisk signifikans (innefattar varianter i gener som finns med i internationella/nationella riktlinjer)",
                    2: "Variant av potentiell klinisk signifikans (innefattar varianter i gener som finns med i publikationer)",
                    3: "Variant av oklar klinisk signifikans (innefattar varianter i gener i få eller inga publikationer)",
                }
            )
        sections.append(
            _table(
                "classification",
                "",
                ["", ""],
                [[_format_tier(tier), text] for tier, text in legend.items()],
                caption=(
                    f"Tabell {table_number}: Förklaring av klassificering"
                    if analyte == "dna"
                    else "Tabell: Förklaring av klassificering"
                ),
                style="reference",
                show_header=False,
                column_options={"0": {"width": 12}, "1": {"width": 88}},
            )
        )
        sections.append(
            {
                "key": "references",
                "kind": "references",
                "text": "[1] Standards and guidelines for the interpretation and reporting of sequence variants in cancer. Li et al, Journal of Molecular Diagnostics, 2017.",
            }
        )
    for key in ("coyote_logo", "center_logo", "accreditation_logo"):
        if branding.get(key) and not branding[key].startswith("data:image/"):
            raise ValueError("Report artwork must already be embedded")
    return {
        "preset": "coyote3",
        "analyte": analyte,
        "language": "sv",
        "title": str(
            (
                (config.get("reporting") or {}).get("report_header")
                if analyte == "dna"
                else context.get("report_header")
            )
            or ""
        )
        + f" - {sample.get('name', '')}",
        "report": _metadata(context, analyte),
        "layout": {"metadata_heading": "Patient/Analysinformation", "document_label": ""},
        "branding": {
            "organization": branding.get("center_name") or context.get("organization_name") or "",
            "department": branding.get("center_department", ""),
            "address": branding.get("center_address", ""),
            "application_logo": branding.get("coyote_logo"),
            "center_logo": branding.get("center_logo"),
            "accreditation_logo": branding.get("accreditation_logo")
            if context.get("assay_accredited") is True
            else None,
            "accredited": context.get("assay_accredited") is True,
        },
        "provenance": {
            "application_name": "Coyote3",
            "application_version": __version__,
            "pipeline_name": str(sample.get("pipeline") or ""),
            "pipeline_version": str(sample.get("pipeline_version") or ""),
            "assay_name": str(sample.get("asp_id") or ""),
        },
        "sections": sections,
    }


def _biomarkers(context: dict, sections: list[dict], details: list[dict], empty: dict) -> list[str]:
    """Preserve paired MSI selection, clinical assessments and measured biomarker evidence.

    Args:
        context: Prepared clinical inputs and report presentation configuration.
        sections: Summary sections receiving biomarker rows or empty messages.
        details: Existing detail cards, appended in their established analysis order.
        empty: Per-analysis empty-result wording.

    Returns:
        Analyses represented in the combined summary table, independent of display labels.
    """
    data = context.get("report_sections_data") or {}
    enabled = context.get("report_sections") or []
    rows = []
    row_analyses = []
    methods_by_analysis = [
        ("HRD", ["HRD"]),
        ("MSI", ["MSIP"] if context["sample"].get("paired") else ["MSIS"]),
        ("TMB", ["TMB"]),
        ("BIOMARKER", [None]),
    ]
    order = ((context.get("assay_config") or {}).get("reporting") or {}).get(
        "summary_table_order"
    ) or []
    for analysis, methods in methods_by_analysis:
        if analysis not in enabled:
            continue
        found = False
        for index, row in enumerate(
            data.get("biomarkers" if analysis == "BIOMARKER" else analysis.lower()) or []
        ):
            for method in methods:
                measurement = row if method is None else row.get(method)
                if not measurement:
                    continue
                found = True
                name = method or row.get("biomarker") or "Biomarkör"
                assessment = (measurement.get("clinical_assessment") or {}).get(
                    "value"
                ) or "Ej bedömd"
                rows.append([name, assessment])
                row_analyses.append(analysis)
                if analysis == "HRD":
                    fields = [
                        (label, measurement.get(key))
                        for label, key in [
                            ("Summa", "sum"),
                            ("TAI", "tai"),
                            ("HRD", "hrd"),
                            ("LST", "lst"),
                        ]
                    ]
                elif analysis == "MSI":
                    fields = [
                        ("Andel", f"{measurement.get('per', '-')}%"),
                        (
                            "Instabila / totalt",
                            f"{measurement.get('som', '-')} / {measurement.get('tot', '-')}",
                        ),
                    ]
                elif analysis == "TMB":
                    fields = [
                        (
                            "TMB",
                            f"{measurement.get('value', '-')} {measurement.get('unit') or 'mut/Mb'}",
                        )
                    ]
                else:
                    fields = [
                        (key, value)
                        for key, value in row.items()
                        if key
                        not in {
                            "_id",
                            "SAMPLE_ID",
                            "name",
                            "biomarker",
                            "clinical_assessment",
                            "assessment_history",
                        }
                    ]
                if method is not None:
                    fields.append(("Klinisk bedömning", assessment))
                if fields:
                    details.append(
                        _detail(
                            f"biomarker-{analysis.lower()}-{index}",
                            f"{name} · {row.get('name') or 'Biomarkör'}",
                            fields,
                        )
                    )
        if not found:
            sections.append(
                {"key": f"empty-{analysis.lower()}", "kind": "text", "text": empty[analysis]}
            )
    if rows:
        sections.append(
            _table(
                "biomarkers",
                "Kliniskt relevanta biomarkörer",
                ["Biomarkör", "Klinisk bedömning"],
                [
                    row
                    for _, row in sorted(
                        zip(row_analyses, rows),
                        key=lambda entry: analysis_priority([entry[0]], order),
                    )
                ],
            )
        )
    return row_analyses
