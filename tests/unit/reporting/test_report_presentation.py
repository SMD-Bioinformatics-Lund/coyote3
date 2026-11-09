"""Modern empty-result wording and compact metadata preserve clinical content."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import TableCellBox, TableRowBox, TextBox

from api.config import report_presentation
from api.presentation.reports.branding import render_branded_report_html
from coyote3.application.reporting.dna_report_payload import sort_by_class_and_af
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.application.reporting.report_renderer import render_report_html
from tests.unit.reporting.test_external_report_templates import context


def structural_context():
    """Supply synthetic findings for compact summary and detailed evidence checks."""
    inputs = empty_context()
    inputs["sample"]["paired"] = True
    inputs["report_scope_label"] = "Synthetic diagnosis · parad analys"
    inputs["latest_sample_comment_text"] = "Synthetic reviewed conclusion."
    inputs["report_sections"] = ["SNV", "CNV", "TRANSLOCATION"]
    inputs["report_sections_data"].update(
        snvs=[
            {
                "symbol": "TP53",
                "chr": "17",
                "pos": 10001,
                "class_type": "Somatisk",
                "variant_class": "SNV",
                "var_type": "snv",
                "feature": "ENST_SYNTHETIC_001",
                "consequence": "missense",
                "exon": ["4/11"],
                "variant": "p.(K4E)",
                "cdna": "c.10A>G",
                "af": 0.4,
                "indel_size": 0,
                "class": 1,
                "class_short_desc": "Synthetic clinical significance",
                "class_long_desc": "Synthetic interpretation",
                "protein_changes": ["p.(K4E)", "p.(Lys4Glu)"],
                "global_annotations": [],
                "annotations_interesting": {},
            }
        ],
        cnvs=[
            {
                "genes": [{"gene": "MYC", "class": 1}],
                "chr": "8",
                "start": 10001,
                "end": 20000,
                "size": 10000,
                "type": "DUP",
                "ratio": 1,
                "nprobes": 20,
                "classification": {"class": 2},
                "global_annotations": [],
            }
        ],
        translocs=[
            {
                "CHROM": "22",
                "POS": 10001,
                "ALT": "N[9:20001[",
                "INFO": {"ANN": [{"Gene_Name": "BCR&ABL1", "Rank": "2/10"}]},
                "GT": [{"type": "case", "PR": [100, 20], "SR": [50, 0]}],
                "classification": {"class": 1},
                "global_annotations": [],
            }
        ],
    )
    return inputs


def test_modern_structural_tables_preserve_tiers_copy_numbers_and_zero_reads():
    """New tables render clinical fields and retain zero-valued structural evidence."""
    inputs = structural_context()
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=html).etree_element
    expected_headers = {
        "snvs": ["Gen", "Kromosom", "Exon", "HGVS", "VAF", "Tier", "Klassificering"],
        "cnvs": ["Gen", "Kromosom", "Typ (CN)", "Storlek", "Tier", "Klassificering"],
        "translocations": ["Fusion", "Lokus", "Exon", "Tier", "Klassificering"],
    }
    for analysis, labels in expected_headers.items():
        table = root.find(f'.//section[@id="{analysis}"]/table')
        assert [cell.text for cell in table.findall("./thead/tr/th")] == labels
    cnv = root.find('.//section[@id="cnvs"]/table')
    assert "DUP (4.00)" in " ".join(cnv.itertext())
    assert cnv.findall("./tbody/tr/td")[4].text == "II"
    translocation = root.find('.//section[@id="translocations"]/table')
    assert translocation.findall("./tbody/tr/td")[3].text == "I"
    read_row = next(
        row
        for table in root.findall('.//article[@class="finding-detail"]/table')
        for row in table.findall(".//tr")
        if row.find("th") is not None and row.find("th").text == "Prov"
    )
    assert [cell.text for cell in read_row] == [
        "Prov",
        "case",
        "Paired reads (PR)",
        "100/20",
        "Split reads (SR)",
        "50/0",
    ]
    assert all("colspan" not in cell.attrib for cell in read_row.findall("td"))
    snv = root.find('.//section[@id="snvs"]/table')
    cells = snv.findall("./tbody/tr/td")
    assert ["".join(cell.itertext()).strip() for cell in cells] == [
        "TP53",
        "17",
        "4/11",
        "p.(K4E)",
        "40%",
        "I",
        "Synthetic clinical significance",
    ]
    detail_text = " ".join(
        text
        for table in root.findall('.//article[@class="finding-detail"]/table')
        for text in table.itertext()
    )
    for value in [
        "MYC",
        "BCR::ABL1",
        "100/20",
        "50/0",
        "p.(Lys4Glu)",
        "Somatisk SNV",
        "ENST_SYNTHETIC_001",
        "missense",
        "10001",
        "Tier I",
        "Gen",
        "Typ",
        "Transkript",
        "Konsekvens",
        "cDNA-förändring",
        "Proteinförändring",
        "Kromosom",
        "Position (hg38)",
        "Frekvens",
        "Exon",
        "Intron",
        "Klassificering",
    ]:
        assert value in detail_text
    assert "p.(K4E)" not in detail_text
    assert inputs["report_sections_data"]["snvs"][0]["protein_changes"] == [
        "p.(K4E)",
        "p.(Lys4Glu)",
    ]
    assert "Synthetic diagnosis · parad analys" in html


@pytest.mark.parametrize(
    "exon,intron,expected_exon,expected_intron",
    [(["4", "11"], [], "4/11", "-"), ([], ["3", "10"], "-", "3/10"), ([], [], "-", "-")],
)
def test_detail_exon_and_intron_have_separate_cells(exon, intron, expected_exon, expected_intron):
    """Transcript identifiers remain separate from recorded exon and intron ranks."""
    inputs = structural_context()
    inputs["report_sections_data"]["snvs"][0].update(exon=exon, intron=intron)
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=html).etree_element
    table = root.find('.//section[@id="snv-0"]//table')
    fields = {}
    for row in table.findall(".//tr"):
        cells = list(row)
        for index, cell in enumerate(cells[:-1]):
            if cell.get("class") == "report_key":
                fields[cell.text] = "".join(cells[index + 1].itertext()).strip()
    assert fields["Transkript"] == "ENST_SYNTHETIC_001"
    assert fields["Exon"] == expected_exon
    assert fields["Intron"] == expected_intron


@pytest.mark.parametrize("tier,numeral", [(1, "I"), (2, "II"), (3, "III"), (4, "IV")])
def test_rna_summary_uses_roman_tiers_and_details_keep_labels(tier, numeral):
    """RNA summary tiers are compact while the detailed classification keeps Tier."""
    inputs = empty_context("rna")
    inputs["class_desc"] = {tier: "Synthetic interpretation"}
    inputs["fusions"] = [
        {
            "gene1": "BCR",
            "gene2": "ABL1",
            "classification": {"class": tier},
            "global_annotations": [],
            "calls": [
                {
                    "selected": 1,
                    "spanpairs": 12,
                    "spanreads": 7,
                    "breakpoint1": "22:10001",
                    "breakpoint2": "9:20001",
                }
            ],
        }
    ]
    html = render_report_html(
        template_name="report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="rna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=html).etree_element
    summary = root.find('.//section[@id="fusions"]/table')
    assert summary.findall("./tbody/tr/td")[3].text == numeral
    detail = root.find('.//article[@class="finding-detail"]/table')
    assert f"Tier {numeral}" in " ".join(detail.itertext())


@pytest.mark.parametrize("classification", [None, {}, {"class": 0}, {"class": 999}])
def test_missing_detail_classification_is_one_plain_hyphen(classification):
    """Unknown structural classifications do not render repeated missing-value separators."""
    inputs = structural_context()
    inputs["report_sections_data"]["cnvs"][0]["classification"] = classification
    inputs["report_sections_data"]["translocs"][0]["classification"] = classification
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=html).etree_element
    classifications = []
    for table in root.findall('.//article[@class="finding-detail"]/table'):
        heading = "".join(table.find(".//th").itertext()).strip()
        if heading in {"MYC", "BCR::ABL1"}:
            cell = next(
                list(row)[index + 1]
                for row in table.findall(".//tr")
                for index, label in enumerate(row)
                if label.tag == "th" and label.text == "Klassificering"
            )
            classifications.append("".join(cell.itertext()).strip())
    assert classifications == ["-", "-"]
    for analysis in ["cnvs", "translocations"]:
        summary = root.find(f'.//section[@id="{analysis}"]/table')
        assert summary.findall("./tbody/tr/td")[-1].text == "-"


@pytest.mark.parametrize("section", ["snvs", "germline_snvs"])
def test_snv_summary_keeps_compact_tiers_and_protein_notation_in_clinical_order(section):
    """Both SNV summaries retain tier/VAF ordering and short amino-acid notation."""
    inputs = structural_context()
    original = inputs["report_sections_data"]["snvs"][0]
    rows = [
        {**original, "symbol": name, "class": tier, "af": af}
        for name, tier, af in [
            ("SYNTHETIC_II", 2, 0.9),
            ("SYNTHETIC_I_LOW", 1, 0.1),
            ("SYNTHETIC_IV", 4, 0.5),
            ("SYNTHETIC_I_HIGH", 1, 0.8),
            ("SYNTHETIC_III", 3, 0.7),
            ("SYNTHETIC_I_UNKNOWN", 1, None),
        ]
    ]
    inputs["report_sections_data"]["snvs"] = []
    inputs["report_sections_data"][section] = sort_by_class_and_af(rows)
    html = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=html).etree_element
    table = root.find(f'.//section[@id="{section}"]/table')
    cells = [
        ["".join(cell.itertext()).strip() for cell in row.findall("td")]
        for row in table.findall("./tbody/tr")
    ]
    assert [row[0] for row in cells] == [
        "SYNTHETIC_I_HIGH",
        "SYNTHETIC_I_LOW",
        "SYNTHETIC_I_UNKNOWN",
        "SYNTHETIC_II",
        "SYNTHETIC_III",
        "SYNTHETIC_IV",
    ]
    assert [row[5] for row in cells] == ["I", "I", "I", "II", "III", "IV"]
    assert all(row[3] == "p.(K4E)" for row in cells)
    assert original["variant"] == "p.(K4E)"


def empty_context(analyte="dna"):
    """Prepare enabled sections with no reportable findings and complete metadata."""
    inputs = context()
    inputs["sample"].update(
        case_id="SYNTHETIC_CASE",
        control_id="SYNTHETIC_CONTROL",
        sample_no=2,
    )
    inputs["assay_config"]["reporting"]["report_method"] = "Synthetic method"
    inputs["report_date"] = "2026-10-25"
    inputs["report_timestamp"] = "SYNTHETIC_REPORT_ID"
    inputs["report_sections"] = [
        "SNV",
        "CNV",
        "TRANSLOCATION",
        "HRD",
        "MSI",
        "TMB",
        "BIOMARKER",
        "PGX",
    ]
    inputs["report_sections_data"] = {
        "snvs": [],
        "germline_snvs": [],
        "cnvs": [],
        "translocs": [],
        "hrd": [],
        "msi": [],
        "tmb": [],
        "biomarkers": [],
        "pgx": [],
    }
    if analyte == "rna":
        inputs["report_sections"] = ["FUSION", "PGX"]
        inputs["pgx"] = []
    return inputs


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_markdown_conclusion_preserves_formatting_and_renders_bordered_table(analyte):
    """Authored Markdown keeps its structure and prints a legible table in the conclusion."""
    inputs = empty_context(analyte)
    inputs["latest_sample_comment_text"] = (
        "## Synthetic conclusion\n\n**Reviewed** with *context*.\n\n"
        "- First item\n- Second item\n\n"
        "> Synthetic quotation\n\n"
        "| Column | Value |\n| --- | --- |\n| item | result |\n"
    )
    html = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
    )
    for fragment in (
        "<h2>Synthetic conclusion</h2>",
        "<strong>Reviewed</strong>",
        "<em>context</em>",
        "<ul>",
        "<li>First item</li>",
        "<blockquote>",
        "<th>Column</th>",
        "<td>result</td>",
    ):
        assert fragment in html
    document = HTML(string=html).render()
    cells = []
    for page in document.pages:
        for box in page._page_box.descendants():
            if not isinstance(box, TableCellBox):
                continue
            text = "".join(child.text for child in box.descendants() if isinstance(child, TextBox))
            if text in {"Column", "Value", "item", "result"}:
                cells.append(box)
                assert box.border_top_width > 0
                assert box.border_right_width > 0
                assert box.border_bottom_width > 0
                assert box.border_left_width > 0
                assert box.style["font_size"] == pytest.approx(8 * 96 / 72)
                assert box.style["font_weight"] == 400
                assert box.padding_top == 2
    assert len(cells) == 4


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_summary_table_fills_printable_width_and_wraps_long_cell_text(analyte):
    """A plain conclusion table retains long content within the report margins."""
    inputs = empty_context(analyte)
    long_value = "SYNTHETIC_SEQUENCE_" * 25
    inputs["latest_sample_comment_text"] = (
        f"| Label | Value |\n| --- | --- |\n| Synthetic | {long_value} |\n"
    )
    html = HTML(
        string=render_report_html(
            template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
            template_context=inputs,
            snapshot_rows=[],
            analyte=analyte,
            preview=True,
            layout="modern",
        )
    )
    summary = html.etree_element.find('.//section[@id="conclusion"]')
    cell_elements = set(summary.findall(".//th") + summary.findall(".//td"))
    document = html.render()
    cells = []
    for page in document.pages:
        left = page._page_box.content_box_x()
        right = left + page._page_box.width
        for box in page._page_box.descendants():
            if isinstance(box, TableCellBox) and box.element in cell_elements:
                cells.append(box)
                for text in box.descendants():
                    if isinstance(text, TextBox):
                        assert text.position_x >= left - 1
                        assert text.position_x + text.width <= right + 1
        on_page = [
            box
            for box in page._page_box.descendants()
            if isinstance(box, TableCellBox) and box.element in cell_elements
        ]
        if on_page:
            # The package places the table inside its padded conclusion panel.
            assert min(box.position_x for box in on_page) >= left
            assert max(box.position_x + box.border_width() for box in on_page) <= right
    rendered = "".join(
        text.text for box in cells for text in box.descendants() if isinstance(text, TextBox)
    )
    assert long_value in rendered


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_empty_enabled_sections_show_configured_text_without_tables(analyte):
    inputs = empty_context(analyte)
    original = deepcopy(inputs)
    defaults = ReportPresentation().empty_results.model_dump()
    messages = {key: f"Synthetic {key} <empty> & result" for key in defaults}
    output = render_report_html(
        template_name="dna_report.html" if analyte == "dna" else "report_fusion.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte=analyte,
        preview=True,
        layout="modern",
        presentation=ReportPresentation(empty_results=messages),
    )
    document = HTML(string=output).etree_element
    assert all(
        section.get("id") == "classification"
        for section in document.findall(".//main/section")
        if section.find("table") is not None
    )
    paragraphs = ["".join(node.itertext()) for node in document.findall('.//p[@class="empty"]')]
    paragraphs.extend(
        "".join(section.find("div").itertext())
        for section in document.findall(".//section")
        if section.get("id", "").startswith("empty-")
    )
    expected_keys = defaults.keys() - {"FUSION"} if analyte == "dna" else {"FUSION", "PGX"}
    assert set(paragraphs) == {messages[key] for key in expected_keys}
    assert len(paragraphs) == len(expected_keys)
    assert "<empty>" not in output
    assert "Detekterade fusioner" not in "".join(document.itertext())
    assert inputs == original


def test_disabled_sections_do_not_emit_empty_messages():
    inputs = empty_context()
    inputs["report_sections"] = []
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    assert not HTML(string=output).etree_element.findall('.//p[@class="empty"]')


def test_manual_assessments_are_separate_from_scores_and_classifications():
    """Report summaries show authored values, while detailed evidence retains the scores."""
    inputs = empty_context()
    inputs["report_sections"] = ["SNV", "TMB", "MSI"]
    inputs["report_sections_data"]["snvs"] = [
        {
            "symbol": f"GENE_{tier}",
            "variant": "p.Synthetic",
            "indel_size": 0,
            "af": 0.4,
            "class": tier,
            "class_short_desc": f"Tier {tier}",
            "global_annotations": [],
        }
        for tier in [1, 2]
    ]
    inputs["report_sections_data"]["tmb"] = [
        {"name": "source", "TMB": {"value": 0, "clinical_assessment": {"value": "HIGH"}}}
    ]
    inputs["report_sections_data"]["msi"] = [
        {
            "name": "source",
            "MSIS": {"per": 0, "som": 0, "tot": 100},
            "MSIP": {"per": 1, "som": 1, "tot": 100, "clinical_assessment": {"value": "LOW"}},
        }
    ]
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    html = HTML(string=output)
    summary = html.etree_element.find('.//section[@id="biomarkers"]/table')
    text = " ".join(summary.itertext())
    assert all(value in text for value in ["MSIS", "HIGH", "Ej bedömd"])
    assert "MSIP" not in text and "LOW" not in text
    assert "source" not in text
    assert "mut/Mb" not in text
    assert output.index('id="biomarker-tmb-0"') > output.index("Detekterade varianter")
    detail = html.etree_element.find('.//section[@id="biomarker-tmb-0"]//table')
    assert "0 mut/Mb" in "".join(detail.itertext())
    rows = html.etree_element.findall('.//section[@id="snvs"]/table/tbody/tr')
    assert [row.findall("td")[-1].text for row in rows] == ["Tier 1", "Tier 2"]
    document = html.render()
    summary_cells = set(cell for row in rows for cell in row.findall("td"))
    rendered_cells = [
        box
        for page in document.pages
        for box in page._page_box.descendants()
        if isinstance(box, TableCellBox) and box.element in summary_cells
    ]
    assert len(rendered_cells) == 14
    for box in rendered_cells:
        assert box.style["font_weight"] == 400


@pytest.mark.parametrize(
    "paired,method,excluded", [(False, "MSIS", "MSIP"), (True, "MSIP", "MSIS")]
)
def test_msi_report_uses_pairing_method_without_sample_name_column(paired, method, excluded):
    inputs = empty_context()
    inputs["sample"]["paired"] = paired
    inputs["report_sections"] = ["MSI"]
    inputs["report_sections_data"]["msi"] = [
        {
            "name": "SYNTHETIC_SOURCE_NAME",
            "MSIS": {"per": 0, "som": 0, "tot": 100},
            "MSIP": {"per": 5, "som": 5, "tot": 100},
        }
    ]
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    root = HTML(string=output).etree_element
    summary = root.find('.//section[@id="biomarkers"]/table')
    assert len(summary.findall(".//thead/tr/th")) == 2
    text = " ".join(summary.itertext())
    assert method in text and excluded not in text
    assert "SYNTHETIC_SOURCE_NAME" not in text
    details = root.findall('.//section[@id="biomarker-msi-0"]//table')
    assert len(details) == 1
    detail_text = " ".join(details[0].itertext())
    assert method in detail_text and excluded not in detail_text


def test_populated_dna_sections_retain_every_finding_table():
    inputs = empty_context()
    variant = {
        "symbol": "SYNTHETIC_GENE",
        "variant": "p.Synthetic",
        "cdna": "c.Synthetic",
        "af": 0.5,
        "indel_size": 0,
        "class_short_desc": "Synthetic class",
        "class_long_desc": "Synthetic interpretation",
        "class": 2,
        "global_annotations": [],
        "protein_changes": [],
    }
    inputs["report_sections_data"].update(
        snvs=[variant],
        germline_snvs=[variant],
        cnvs=[{"genes": [{"gene": "SYNTHETIC_GENE", "class": 1}], "size": 10, "ratio": 1}],
        translocs=[
            {"INFO": {"MANE_ANN": {"Gene_Name": "SYNTHETIC_A&SYNTHETIC_B", "HGVSp": "p.Synthetic"}}}
        ],
        hrd=[{"HRD": {"sum": 3, "tai": 1, "hrd": 1, "lst": 1}}],
        msi=[{"MSIS": {"per": 1, "som": 1, "tot": 100}}],
        tmb=[{"TMB": {"value": 1}}],
        biomarkers=[{"name": "Synthetic biomarker", "value": 1}],
        pgx=[{"gene": "SYNTHETIC_GENE", "result": "Synthetic phenotype"}],
    )
    outputs = {}
    for layout in ["legacy", "modern"]:
        output = render_report_html(
            template_name="dna_report.html",
            template_context=inputs,
            snapshot_rows=[],
            analyte="dna",
            preview=True,
            layout=layout,
        )
        root = HTML(string=output).etree_element
        tables = (
            root.findall('.//table[@class="variant_table"]')
            if layout == "legacy"
            else [
                root.find(f'.//section[@id="{key}"]/table')
                for key in ["snvs", "germline_snvs", "cnvs", "translocations", "pgx"]
            ]
        )
        assert len(tables) == (9 if layout == "legacy" else 5)
        assert not root.findall('.//p[@class="report-empty-result"]')
        outputs[layout] = [
            [
                " ".join("".join(cell.itertext()).split())
                for cell in table.iter()
                if cell.tag in {"td", "th"}
            ]
            for table in tables
        ]
        if layout == "modern":
            summary = root.find('.//section[@id="biomarkers"]/table')
            assert len(summary.findall(".//tbody/tr")) == 4
            assert "Ej bedömd" in "".join(summary.itertext())
            details = [
                section.find(".//table")
                for section in root.findall(".//section")
                if section.get("id", "").startswith("biomarker-")
            ]
            assert len(details) == 4
            assert "Synthetic biomarker" in "".join(details[-1].itertext())
            assert "mut/Mb" in "".join(details[2].itertext())
    assert outputs["modern"][0][:7] == [
        "Gen",
        "Kromosom",
        "Exon",
        "HGVS",
        "VAF",
        "Tier",
        "Klassificering",
    ]
    assert "SYNTHETIC_GENE" in outputs["modern"][0]
    assert "Synthetic class" in outputs["modern"][0]
    assert "SYNTHETIC_A::SYNTHETIC_B" in outputs["modern"][3]
    assert outputs["modern"][-1] == outputs["legacy"][-1]


def test_center_wording_is_optional_and_reloaded_without_aspc_edits(monkeypatch, tmp_path):
    monkeypatch.setattr(report_presentation, "CENTER_CONFIG_DIR", tmp_path)
    assert report_presentation.load_report_presentation() == ReportPresentation()
    config_file = tmp_path / "report_presentation.toml"
    config_file.write_text('[empty_results]\nCNV = "Synthetic CNV message"\n')
    settings = report_presentation.load_report_presentation()
    assert settings.empty_results.CNV == "Synthetic CNV message"
    assert settings.empty_results.SNV == ReportPresentation().empty_results.SNV
    inputs = empty_context()
    for message in ["First configured message", "Updated configured message"]:
        config_file.write_text(f'[empty_results]\nSNV = "{message}"\n')
        output = render_branded_report_html(
            config={},
            template_name="dna_report.html",
            template_context=inputs,
            snapshot_rows=[],
            analyte="dna",
            preview=True,
            layout="modern",
        )
        assert message in output

    inputs["report_presentation"] = {"empty_results": {"SNV": "Captured for reviewed render"}}
    output = render_branded_report_html(
        config={},
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    assert "Captured for reviewed render" in output
    assert "Updated configured message" not in output


@pytest.mark.parametrize(
    "content",
    [
        '[empty_results]\nSNVV = "Typo"',
        '[empty_results]\nSNV = "   "',
        "[empty_results]\nSNV = 12",
        "[empty_results",
    ],
)
def test_invalid_center_wording_fails_instead_of_silently_using_defaults(
    monkeypatch, tmp_path, content
):
    monkeypatch.setattr(report_presentation, "CENTER_CONFIG_DIR", tmp_path)
    (tmp_path / "report_presentation.toml").write_text(content)
    with pytest.raises((ValueError, ValidationError)):
        report_presentation.load_report_presentation()


def test_metadata_is_compact_in_a4_output_without_losing_fields():
    output = render_report_html(
        template_name="dna_report.html",
        template_context=empty_context(),
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
        organization_name="Synthetic institution",
        generated_by="Synthetic reviewer",
    )
    document = HTML(string=output).render()
    metadata = [
        box
        for page in document.pages
        for box in page._page_box.descendants()
        if box.element_tag == "section" and box.element.get("class") == "report-metadata"
    ]
    assert len(metadata) == len(document.pages)
    assert all(box.height < 150 for box in metadata)
    metadata_element = HTML(string=output).etree_element.find(
        './/section[@class="report-metadata"]'
    )
    text = " ".join(metadata_element.itertext())
    for value in [
        "Patientnamn",
        "Personnummer",
        "SYNTHETIC_CASE",
        "SYNTHETIC_CONTROL",
        "Synthetic method",
        "Synthetic institution",
        "Synthetic reviewer",
        "SYNTHETIC_REPORT_ID",
    ]:
        assert value in text


def test_short_report_uses_compact_rows_and_starts_conclusion_on_a_new_page():
    """Summary findings start on page one; the conclusion begins on a separate page."""
    inputs = context()
    inputs["report_sections"] = ["SNV"]
    inputs["report_sections_data"] = {
        "snvs": [
            {
                "symbol": "SYNTHETIC_GENE",
                "variant": "p.Val1Ala",
                "cdna": "c.2T>C",
                "af": 0.42,
                "indel_size": 0,
                "class": 1,
                "class_short_desc": "Tier I",
                "class_long_desc": "Synthetic interpretation",
                "global_annotations": [],
                "annotations_interesting": {},
            }
        ]
    }
    inputs["latest_sample_comment_text"] = "SYNTHETIC_CONCLUSION"
    output = render_report_html(
        template_name="dna_report.html",
        template_context=inputs,
        snapshot_rows=[],
        analyte="dna",
        preview=True,
        layout="modern",
    )
    html = HTML(string=output)
    document = html.render()
    first_page_text = " ".join(
        box.text for box in document.pages[0]._page_box.descendants() if isinstance(box, TextBox)
    )
    assert "SYNTHETIC_CONCLUSION" not in first_page_text
    assert "Analysresultat" in first_page_text
    second_page_text = " ".join(
        box.text for box in document.pages[1]._page_box.descendants() if isinstance(box, TextBox)
    )
    assert "SYNTHETIC_CONCLUSION" in second_page_text
    assert "Detekterade varianter" not in second_page_text
    third_page_text = " ".join(
        box.text for box in document.pages[2]._page_box.descendants() if isinstance(box, TextBox)
    )
    assert "Detekterade varianter" in third_page_text
    assert "SYNTHETIC_CONCLUSION" not in third_page_text
    table = html.etree_element.find('.//section[@id="snvs"]/table')
    rows = set(table.findall(".//tr"))
    rendered_rows = [
        box
        for page in document.pages
        for box in page._page_box.descendants()
        if isinstance(box, TableRowBox) and box.element in rows
    ]
    assert len(rendered_rows) == 2
    # Seven-column summaries can wrap gene names. Compactness is governed by
    # cell padding rather than requiring clinical text to fit on a single line.
    cells = [
        cell for row in rendered_rows for cell in row.children if isinstance(cell, TableCellBox)
    ]
    assert len(cells) == 14
    assert all(
        cell.style["padding_top"].value <= 2 and cell.style["padding_bottom"].value <= 2
        for cell in cells
    )
