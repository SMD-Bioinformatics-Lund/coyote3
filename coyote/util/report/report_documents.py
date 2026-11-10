"""Build conditional smd-reports JSON from prepared production report data.

Queries, finding selection, annotation, and snapshots remain in the existing DNA
and RNA workflows. These builders express their display content without rendering
or parsing a report HTML document.
"""

import re
from datetime import date, datetime
from html import escape, unescape
from typing import Any
from xml.etree import ElementTree

import tinyhtml5
from flask import current_app
from markupsafe import Markup

from coyote.__version__ import __version__

LABORATORY = "Centrum för molekylär diagnostik (CMD) och Klinisk genetik och patologi"
REFERENCE = (
    "[1] Standards and guidelines for the interpretation and reporting of sequence "
    "variants in cancer. Li et al, Journal of Molecular Diagnostics, 2017."
)
DNA_TIERS = [
    [
        "Tier I",
        "Variant av stark klinisk signifikans (genmutationer som är diagnostiska, "
        "behandlingsstyrande eller riskstratifierande enligt gällande riktlinjer)",
    ],
    [
        "Tier II",
        "Variant av potentiell klinisk signifikans (mutationer i gener beskrivna "
        "i ett flertal publikationer)",
    ],
    [
        "Tier III",
        "Variant av oklar klinisk signifikans (mutationer i gener beskrivna "
        "i ett fåtal publikationer)",
    ],
    ["Tier IV", "Variant bedömd som benign eller sannolikt benign"],
]
RNA_TIERS = [
    [
        "Tier I",
        "Variant av stark klinisk signifikans (innefattar varianter i gener som "
        "finns med i internationella/nationella riktlinjer)",
    ],
    [
        "Tier II",
        "Variant av potentiell klinisk signifikans (innefattar varianter i gener "
        "som finns med i publikationer)",
    ],
    [
        "Tier III",
        "Variant av oklar klinisk signifikans (innefattar varianter i gener "
        "i få eller inga publikationer)",
    ],
    ["Tier IV", "Variant bedömd som benign eller sannolikt benign"],
]


def _value(record: dict, key: str) -> str:
    """Return a prepared field using the legacy Jinja null/missing distinction.

    Args:
        record: Prepared metadata or finding.
        key: Field to display; a missing field produces empty text.

    Returns:
        String value, including literal None for an explicit null.
    """
    return str(record[key]) if key in record else ""


def _filter(name: str, value: Any) -> str:
    """Apply an existing production display filter.

    Args:
        name: Registered Jinja filter name.
        value: Value accepted by that filter.

    Returns:
        The production display string.
    """
    return str(current_app.jinja_env.filters[name](value))


def _rich_text(html: str | None) -> str:
    """Normalize existing rich-text inputs for the package Markdown sanitizer.

    Args:
        html: Configured analysis text or already escaped/formatted comment text.
            This is source narrative content, never a rendered report document.

    Returns:
        Supported rich text. Link destinations appear beside their labels because
        smd-reports 0.4.0 strips anchors; application links live outside the report.
    """
    if html is None:
        return "None"
    html = re.sub(r"<([A-Z][A-Z0-9_]+)>", lambda match: escape(match[0]), str(html))
    body = tinyhtml5.parse(html, namespace_html_elements=False).find("body")
    for element in body.iter():
        if element.tag == "a":
            url = element.get("href", "")
            if url and url != "".join(element.itertext()):
                if len(element):
                    element[-1].tail = (element[-1].tail or "") + f" ({url})"
                else:
                    element.text = (element.text or "") + f" ({url})"
            element.tag = "span"
            element.attrib.clear()
        elif element.tag in {"b", "i"}:
            element.tag = {"b": "strong", "i": "em"}[element.tag]
    return escape(body.text or "") + "".join(
        ElementTree.tostring(child, encoding="unicode", method="html") for child in body
    )


def _comment(text: str | None) -> str:
    """Escape and format a production comment for a shared Markdown field.

    Args:
        text: Existing user-authored Markdown, including null or empty comments.

    Returns:
        Rich text produced by the production comment filter.
    """
    return _rich_text(_filter("format_comment", text))


def _conclusion(sample: dict) -> str:
    """Select the last visible sample comment using production array order.

    Args:
        sample: Sample metadata with the existing comments array.

    Returns:
        Formatted conclusion, the existing missing message for an empty array,
        or empty text when every comment is hidden.
    """
    comments = sample.get("comments", [])
    if not comments:
        return "Slutsats saknas!"
    visible = [item for item in comments if item.get("hidden") != 1]
    return _comment(visible[-1].get("text")) if visible else ""


def _base(
    sample: dict,
    analyte: str,
    title: str,
    report_id: str,
    sample_id: str,
    report_date: date,
    author: str,
    fields: list[tuple[str, str]],
) -> dict[str, Any]:
    """Create a shared-template document envelope with ordered metadata.

    Args:
        sample: Sample metadata containing the assay identifier.
        analyte: dna or rna, selecting the installed template identity.
        title: Existing title including the sample display name.
        report_id: Existing displayed report identifier.
        sample_id: Existing displayed Prov-ID.
        report_date: Production local report date.
        author: Existing author display name.
        fields: Additional metadata, excluding automatic sample/date/author/ID fields.

    Returns:
        JSON-ready document with an initially empty section list.
    """
    generated = datetime.combine(report_date, datetime.now().astimezone().timetz())
    return dict(
        preset="coyote3",
        theme="coyote3",
        language="sv",
        analyte=analyte,
        title=title,
        report=dict(
            report_id=report_id,
            sample_id=sample_id,
            generated_at=generated.isoformat(),
            author=author,
            author_label="Rapport genererad av",
            fields=[dict(label=k, value=v) for k, v in fields],
        ),
        provenance=dict(
            application_name="Coyote3",
            application_version=__version__,
            assay_name=sample.get("assay", ""),
        ),
        layout=dict(metadata_heading="Patient/Analysinformation", document_label=""),
        sections=[],
    )


def _table(key: str, heading: str, columns: list[str], rows: list[list], empty: str = "") -> dict:
    """Create a native result table without deriving or sorting clinical values.

    Args:
        key: Unique section identifier.
        heading: Existing section heading.
        columns: Ordered column labels.
        rows: Display values, one per declared column.
        empty: Existing message used when there are no findings.

    Returns:
        JSON table section.
    """
    return dict(
        key=key, kind="table", heading=heading, columns={"sv": columns}, rows=rows, empty_text=empty
    )


def _details(key: str, heading: str, title: str, fields: list[tuple]) -> dict:
    """Create a finding-detail section with optional wide narrative fields.

    Args:
        key: Unique section identifier.
        heading: Group heading, supplied on the first finding only.
        title: Existing finding title.
        fields: Ordered label/value tuples, optionally followed by a Markdown flag.

    Returns:
        JSON detail section with original field ordering.
    """
    return dict(
        key=key,
        kind="details",
        heading=heading,
        record_titles=[title],
        fields_per_row=3,
        columns={"sv": [field[0] for field in fields]},
        rows=[[field[1] for field in fields]],
        full_width_last=False,
        column_options={
            str(i): dict(full_width=True, format="markdown")
            for i, field in enumerate(fields)
            if len(field) > 2 and field[2]
        },
    )


def _dna_detail(variant: dict, index: int) -> dict:
    """Express the production display conditions for one prepared DNA finding.

    Args:
        variant: Existing simple variant from the DNA report workflow.
        index: Position in the existing finding order.

    Returns:
        Native detail section retaining indel boundaries and annotation selection.
    """
    feature = _value(variant, "feature")
    if variant.get("exon"):
        feature += f", exon {variant['exon'][0]}"
    elif variant.get("intron"):
        feature += f", intron {variant['intron'][0]}"
    protein = (
        "\n".join(
            unescape(str(item)) if isinstance(item, Markup) else str(item)
            for item in variant.get("protein_changes", [])
        )
        if variant["indel_size"] < 20
        else _value(variant, "cdna")
    )
    fields = [
        ("Gen", _value(variant, "symbol")),
        ("Typ", f"{_value(variant, 'class_type')} {_value(variant, 'variant_class')}".strip()),
        ("Transkript", feature),
        ("Konsekvens", _value(variant, "consequence")),
        (
            "cDNA-förändring",
            (
                _filter("unesc", variant.get("cdna"))
                if variant.get("var_type") == "snv"
                else _value(variant, "cdna")
            ),
        ),
        ("Proteinförändring", protein),
        ("Kromosom", f"chr{_value(variant, 'chr')}"),
        ("Position (hg38)", _value(variant, "pos")),
        ("Frekvens", _filter("perc_no_dec", variant.get("af"))),
    ]
    if variant.get("class") != 999:
        fields.append(
            (
                "Klassificering",
                f"{_filter('format_tier', variant.get('class'))} - "
                f"{_value(variant, 'class_long_desc')}",
                True,
            )
        )
    if variant.get("global_annotations"):
        interesting = variant.get("annotations_interesting")
        annotations = (
            list(interesting.values())
            if interesting
            else [max(variant["global_annotations"], key=lambda item: item["time_created"])]
        )
        fields.extend(("Kommentar", _comment(item.get("text")), True) for item in annotations)
    name = _filter("unesc", variant.get("variant"))
    title = (
        (f"{_value(variant, 'symbol')}: " + (name if len(name) < 30 else _value(variant, "cdna")))
        if variant.get("variant")
        else ""
    )
    return _details(
        f"dna-finding-{index}", "Detekterade mutationer" if index == 0 else "", title, fields
    )


def build_dna_document(
    *,
    sample: dict,
    assay_config: dict,
    report_sections: list,
    report_sections_data: dict,
    report_date: date,
    report_timestamp: str,
    assay_group: str,
    genes_covered_in_panel: dict,
    author: str,
    asp_url: str,
    germline: bool = False,
) -> dict[str, Any]:
    """Build conditional DNA JSON from the established prepared context.

    Args:
        sample: Existing metadata and ordered comments.
        assay_config: Existing assay reporting configuration.
        report_sections: Enabled production section names.
        report_sections_data: Prepared findings in existing order.
        report_date: Existing displayed report date.
        report_timestamp: Existing displayed report-ID timestamp.
        assay_group: Production assay group controlling sections.
        genes_covered_in_panel: Existing ordered gene-list data.
        author: Report creator display name.
        asp_url: Existing public ASP gene-list URL.
        germline: Existing report-template flag controlling the classification
            explanation and reference. The production caller does not supply it,
            so False retains master's normal display. It is not inferred from findings.

    Returns:
        JSON-ready metadata and conditional sections for smd-reports.
    """
    reporting = assay_config["reporting"]
    fields = [("Patientnamn", "<PATIENT_NAME>"), ("Personnummer", "<PERSONAL_IDENTITY_NUMBER>")]
    if sample.get("sample_no") == 2:
        fields.append(("KontrollProv-ID", _value(sample, "control_id")))
    fields.extend(
        [("Registreringsdatum", "<REGISTRATION_DATE>"), ("Provtyp", "<TUMOR_SAMPLE_TYPE>")]
    )
    if assay_group not in {"swea", "gmsonco"}:
        diagnosis = ""
        if sample.get("assay") == "tumwgs-hema":
            diagnosis = "Hematologisk neoplasi"
        elif sample.get("assay") == "tumwgs-solid" or assay_group == "solid":
            diagnosis = "Solid tumör"
        elif assay_group in {"myeloid", "hematology"}:
            diagnosis = "Hematologisk neoplasi" if sample.get("sample_no") == 2 else "<DIAGNOSIS>"
        fields.append(("Frågeställning", diagnosis))
    fields.extend(
        [
            ("Analysmetod", _value(reporting, "report_method")),
            ("Analys genomförd av", LABORATORY),
            ("Rapportnummer", str(sample.get("report_num", 0) + 1)),
        ]
    )
    report_name = (
        sample.get("case_id", "NONE") + "_" + sample.get("case", {}).get("clarity_id", "NONE")
    )
    if sample.get("control_id"):
        report_name += (
            "-"
            + sample.get("control_id", "NONE")
            + "_"
            + sample.get("control", {}).get("clarity_id", "NONE")
        )
    document = _base(
        sample,
        "dna",
        f"{reporting['report_header']} - {sample['name']}",
        f"{report_name}.{report_timestamp}",
        _value(sample, "case_id"),
        report_date,
        author,
        fields,
    )
    sections = document["sections"]
    sections.append(dict(key="results", kind="text", heading="Analysresultat", text=""))
    variants = report_sections_data["snvs"] if "SNV" in report_sections else []
    if "SNV" in report_sections:
        rows = [
            [
                _value(v, "symbol"),
                _value(v, "cdna") if v["indel_size"] > 20 else _filter("unesc", v.get("variant")),
                _filter("perc_no_dec", v.get("af")),
                _value(v, "class_short_desc"),
            ]
            for v in variants
        ]
        sections.append(
            _table(
                "snvs",
                "Kliniskt relevanta SNVs och små INDELs",
                ["Gen", "Mutation", "Variantfrekvens", "Klassificering"],
                rows,
                "Inga detekterade mutationer",
            )
        )
    sections.append(
        dict(key="notation", kind="text", text="Note: p = protein, c = cDNA, g = genomic")
    )
    if "CNV" in report_sections:
        rows = []
        for cnv in report_sections_data["cnvs"]:
            genes = [gene["gene"] for gene in cnv["genes"] if gene.get("class")]
            other = sum(not gene.get("class") for gene in cnv["genes"])
            names = " ".join(genes) + (f" + {other} other genes" if other else "")
            ratio = cnv["ratio"]
            # Match the Jinja expression: 2 * round(2 ** ratio, 2).
            rows.append(
                [
                    names.strip(),
                    f"{cnv['size']} bp",
                    "AMP" if ratio > 1 else "DUP" if ratio > 0 else "DEL",
                    str(2 * round(2**ratio, 2)),
                ]
            )
        sections.append(
            _table(
                "cnvs",
                "Kliniskt relevanta genspecifika kopietalsförändringar",
                ["Gen(er)", "Storlek", "Typ", "Kopietal"],
                rows,
                "Inga detekterade genspecifika kopietalsförändringar.",
            )
        )
    if "TRANSLOCATION" in report_sections or "FUSION" in report_sections:
        rows = []
        for finding in report_sections_data.get(
            "translocs", report_sections_data.get("fusions", [])
        ):
            info = finding["INFO"]
            annotations = info.get("ANN") or []
            selected = next((item for item in annotations if item.get("selected") == 1), None)
            annotation = selected or info.get("MANE_ANN") or next(iter(annotations), {})
            genes = (annotation.get("Gene_Name") or "").split("&")
            rows.append(
                [
                    f"{genes[0]}::{genes[1] if len(genes) > 1 else ''}",
                    _filter("unesc", annotation.get("HGVSp")),
                ]
            )
        sections.append(
            _table(
                "fusions",
                "Kliniskt relevanta fusioner",
                ["Gener", "HGVS.p"],
                rows,
                "Inga detekterade fusioner",
            )
        )
    # Biomarker display remains disabled, matching production.
    sections.append(
        dict(
            key="conclusion",
            kind="summary",
            heading="Slutsats",
            text=_conclusion(sample),
            format="markdown",
        )
    )
    if report_sections_data.get("cnv_profile_base64"):
        sections.append(
            dict(
                key="cnv-profile",
                kind="image",
                page_break_before=True,
                heading="Kopietalsprofil, genomisk översikt",
                source="data:image/png;base64," + report_sections_data["cnv_profile_base64"],
            )
        )
    for index, variant in enumerate(variants):
        section = _dna_detail(variant, index)
        section["page_break_before"] = index == 0
        sections.append(section)
    sections.append(
        dict(
            key="description",
            kind="description",
            heading="Analysbeskrivning",
            page_break_before=not variants,
            text=_rich_text(reporting.get("report_description")),
            format="markdown",
        )
    )
    table_no = 1
    if assay_group != "tumwgs":
        for name, genes in genes_covered_in_panel.items():
            if name != sample.get("assay"):
                sections.append(
                    dict(
                        key=f"genes-{table_no}",
                        kind="compact_table",
                        heading=f"Tabell {table_no}: Gener inkluderade i {name} insilico-panel",
                        items=genes["covered"],
                        columns=15,
                    )
                )
                table_no += 1
        sections.append(
            dict(
                key="panel-reference",
                kind="text",
                text=(
                    "For complete panel gene lists, and configurations, see here.\n"
                    f"Or, for ASP genelist, visit {asp_url}"
                ),
            )
        )
    if not germline:
        sections.append(
            _table("tiers", f"Tabell {table_no}: Förklaring av klassificering", ["", ""], DNA_TIERS)
        )
        sections.append(
            dict(key="references", kind="references", heading="Referenser", text=REFERENCE)
        )
    return document


def build_rna_document(
    *,
    sample: dict,
    assay: str,
    fusions: list[dict],
    report_header: str,
    analysis_method: str,
    analysis_desc: str | None,
    class_desc: list,
    class_desc_short: list,
    report_date: date,
    author: str,
) -> dict[str, Any]:
    """Build conditional RNA JSON from the production report context.

    Args:
        sample: Existing sample metadata, comments and optional QC values.
        assay: Existing RNA assay identifier.
        fusions: Annotated fusions from the production query.
        report_header: Existing report title.
        analysis_method: Existing method description.
        analysis_desc: Configured analysis HTML, or None.
        class_desc: Existing ordered full tier descriptions.
        class_desc_short: Existing ordered short tier descriptions.
        report_date: Existing local report date.
        author: Report creator display name.

    Returns:
        JSON-ready content retaining report eligibility and ordering.
    """
    fields = [
        ("Patientnamn", "<PATIENT_NAME>"),
        ("Personnummer", "<PERSONAL_IDENTITY_NUMBER>"),
        ("Registreringsdatum", "<REGISTRATION_DATE>"),
        ("Provtyp", "<SAMPLE_TYPE> / RNA"),
        ("Frågeställning", "RNA fusions" if assay == "fusions" else "Gene Panel"),
        ("Analysmetod", str(analysis_method)),
        ("Analys genomförd av", LABORATORY),
    ]
    document = _base(
        sample,
        "rna",
        f"{report_header} - {sample['name']}",
        f"{sample['name']}.{sample.get('report_num', 0) + 1}",
        sample["name"],
        report_date,
        author,
        fields,
    )
    sections = document["sections"]
    eligible = [
        item
        for item in sorted(fusions, key=lambda v: v["classification"]["class"])
        if not item.get("blacklist") and item["classification"]["class"] not in (999, 4)
    ]
    columns = (
        ["Fusion", "Klassificering"]
        if assay == "fusion"
        else ["Fusion/exon skipping", "Klassificering"] if assay == "fusionrna" else ["", ""]
    )
    rows = [
        [
            f"{_value(item, 'gene1')} - {_value(item, 'gene2')}",
            str(class_desc_short[item["classification"]["class"]]),
        ]
        for item in eligible
    ]
    sections.append(_table("fusions", "Analysresultat", columns, rows, "Inga detekterade fusioner"))
    sections.append(
        dict(
            key="conclusion",
            kind="summary",
            heading="Slutsats",
            text=_conclusion(sample),
            format="markdown",
        )
    )
    heading = (
        "Detekterade fusioner"
        if assay == "fusion"
        else "Detekterade fusioner och exon skipping" if assay == "fusionrna" else ""
    )
    for index, fusion in enumerate(eligible):
        selected = next(item for item in fusion["calls"] if item.get("selected") == 1)
        title = f"{_value(fusion, 'gene1')} - {_value(fusion, 'gene2')}"
        spanning = int(_filter("int", selected.get("spanpairs"))) > 0
        fields = [
            ("Gener", title),
            ("Effekt", _value(selected, "effect") if spanning else "NA"),
            (
                "Fusionspunkter",
                (
                    f"{_value(selected, 'breakpoint1')} {_value(selected, 'breakpoint2')}"
                    if spanning
                    else "NA"
                ),
            ),
            ("Antal läsningar", _value(selected, "spanreads")),
            ("Antal läs-par", _value(selected, "spanpairs")),
            (
                "Längsta ankarsekvens",
                f"{selected['longestanchor']} bp" if selected.get("longestanchor") else "NA",
            ),
            (
                "Klassificering",
                f"{_filter('format_tier', fusion['classification']['class'])} - "
                f"{class_desc[fusion['classification']['class']]}",
                True,
            ),
        ]
        if fusion.get("global_annotations"):
            latest = max(fusion["global_annotations"], key=lambda item: item["time_created"])
            fields.append(("Kommentar", _comment(latest.get("text")), True))
        section = _details(f"rna-finding-{index}", heading if index == 0 else "", title, fields)
        section["page_break_before"] = index == 0
        sections.append(section)
    if not eligible:
        sections.append(
            dict(
                key="fusion-details-empty",
                kind="text",
                heading=heading,
                page_break_before=True,
                text="Inga detekterade fusioner",
            )
        )
    if "QC" in sample:
        qc = sample["QC"][0]
        sections.append(
            _table(
                "qc",
                "Kvalitetsvärden",
                ["", ""],
                [
                    ["Antal läspar", f"{qc['tot_reads'] / 1000000:0.0f} miljoner"],
                    ["% mappade läsningar", f"{qc['mapped_pct']}%"],
                ],
            )
        )
    sections.append(
        dict(
            key="description",
            kind="description",
            heading="Analysbeskrivning",
            text=_rich_text(analysis_desc),
            format="markdown",
        )
    )
    sections.append(_table("tiers", "Tabell: Förklaring av klassificering", ["", ""], RNA_TIERS))
    sections.append(dict(key="references", kind="references", heading="Referenser", text=REFERENCE))
    return document
