"""Server-side report template rendering."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import bleach
import markdown
from jinja2 import DictLoader, Environment, select_autoescape

from api.domain.common.reporting import TIER_NAME

REPORT_LAYOUT_TEMPLATE = r"""<!doctype html>
<html lang="sv">
<head>
  <title>{% block title %}{% endblock %}</title>
  <meta charset="utf-8">
  <style>
    @page {
      @top-right{
    font-size: 10px;
    font-family: arial;
    content: "Sida " counter(page) " av " counter(pages);
      }
    }

    body
    {
        margin: 0 0 0 0;
        font-size:11px;
    }

    span.neg {
        color:#0a0;
        font-weight:bold;
    }
    span.pos {
        color:#f00;
        font-weight:bold;
    }

    img.logo {
        width:110px;
        height:auto;
        position:relative;
        left:80%;
        top:20px;
    }

    div.results_summary{
        border: 1px solid #885;
        padding:10px;
        font-size:14px;
        background:#ffc;
        margin-bottom:15px;
    }

    table {
        border-collapse: collapse;
    }

    div.page {
        font-family: arial;
        margin: 20px;
        width:90%;
        position:relative;
        top:-30px;
    }

    table.report_general {
        width: 580px;
        margin-bottom:20px;
        background-color:#f3f3ff;
        border-top: 2px solid #000;
        border-bottom: 2px solid #000;
        font-size:12px;
    }
    table.report_variant {
        width: 600px;
        margin-bottom:40px;
        background-color:#fafafa;
        border: 2px solid #000;
        font-size:10px;
    }

    span.report_medium {
        font-size: 12px;
    }

    span.report_text {
        font-size: 11px;
    }

    span.report_header {
        font-size: 20px;
        font-weight: bold;
        padding-bottom: 7px;
        padding-top: 15px;
        display: block;
    }

    th.report_variant_header {
        border-bottom: 1px solid #000;
        height:23px;
        background-color: #000;
    }

    span.report_variant_header {
        font-size: 14px;
        font-weight: bold;
        padding-left:4px;
        color: #FFF;
    }

    td.report_annotation p {
      margin: 2px;
    }

    th.top_report {
        border:0;
        text-align:left;
        border-bottom: 2px solid #000;
        padding:6px;
        font-weight:bold;
    }

    td.report_key {
        width: 83px;
        border-bottom: 1px solid #ccc;
        border-right: 1px solid #ccc;
        padding:4px;
        margin:0;
        font-weight:bold;
    }

    td.top_report_key {
        width: 130px;
        border-bottom: 1px solid #ccc;
        border-right: 1px solid #ccc;
        padding:5px;
        margin:0;
        font-weight:bold;
    }

    td.report_val {
        background-color: #fff;
        border-bottom: 1px solid #ccc;
        width:105px;
        padding:4px;
    }

    td.var_report_val {
        background-color: #fff;
        border-bottom: 1px solid #ccc;
        border-right: 2px solid #000;
        width:105px;
        padding:4px;
    }

    td.top_report_val {
        background-color: #fff;
        border-bottom: 1px solid #ccc;
        padding:5px;
    }

    td.report_comment {
        background-color: #FFF6DA;
        padding: 1px 4px;
        border: 1px solid #ccc;
        font-size:14px;
    }

    td.report_annotation {
        background-color: #FFC;
        padding:1px 4px;
        border: 1px solid #ccc;
    }

    li{
        margin: 4px 0 4px 0;
    }

    table.info td {
        padding:5px;
        font-size:11px;
        border:1px solid #aaa;
    }

    table.genetable td {
        padding:3px 1px;
        text-align:center;
        font-size:8px;
        border:1px solid #aaa;
    }

    div.wrapping {
        width:105px;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    div.analysis_description {
        max-width:800px;
        padding:0;
        text-align: justify;
    }
    div.conclusion {
        font-size:14px;
        max-width:800px;
    }

    table.variant_table {
        margin:10px 2px;
        border-top: 2px solid #000;
        border-bottom: 2px solid #000;
    }

    table.variant_table td {
        border-bottom: 1px solid #aaa;
        padding:5px 12px;
        font-size:12px;
    }

    table.variant_table th {
        border-bottom: 2px solid #000;
        padding:5px 12px;
        font-size:12px;
        text-align:left;
        font-weight:bold;
        background-color:#f3f3ff;
    }

    .report-preview-card {
        max-width: 768px;
        padding: 1.5rem 0 1.5rem 0;
        background-color: #eef2ff;
        border: 1px solid #c7d2fe;
        border-radius: 1rem;
        text-align: center;
    }

    .report-heading {
        font-size: 1rem;
        font-weight: 600;
        color: #3730a3;
        margin-bottom: 1rem;
        letter-spacing: 0.03em;
    }

    .report-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.5rem 1.25rem;
        background-color: #4f46e5;
        color: white;
        font-size: 0.875rem;
        font-weight: 500;
        border-radius: 0.5rem;
        text-decoration: none;
    }

    #genelist-form,
    #genelist-form * {
      display: none !important;
      visibility: hidden !important;
      width: 0 !important;
      height: 0 !important;
      overflow: hidden !important;
      margin: 0 !important;
      padding: 0 !important;
      border: 0 !important;
    }
  </style>
</head>

<body>
<script type=text/javascript>
  $SCRIPT_ROOT = {{ request.script_root|tojson|safe }};
</script>

<div class="page">
  {% block body %}{% endblock %}
</div>

</body>
</html>
"""


DNA_REPORT_TEMPLATE = r"""{% extends "report_layout.html" %}
{% block title %}DNA Variant Report{% endblock %}
{% block body %}

{% if save != 1 %}
  <div class="report-preview-card">
    <h2 class="report-heading">*** PREVIEW OF REPORT ***</h2>
  </div>
{% endif %}

<span class="report_header">{{ assay_config.reporting.report_header }} - {{ sample.name }}</span>

<div class="report_div">
  <table class='report_general'>
    <tr><td class="top_report_key">Patientnamn</td><td class="top_report_val">&lt;PATIENT_NAME&gt;</td></tr>
    <tr><td class="top_report_key">Personnummer</td><td class="top_report_val">&lt;PERSONAL_IDENTITY_NUMBER&gt;</td></tr>
    <tr><td class="top_report_key">Prov-ID</td><td class="top_report_val">{{ sample.case_id }}</td></tr>
    {% if sample.sample_no == 2 %}
      <tr><td class="top_report_key">KontrollProv-ID</td><td class="top_report_val">{{ sample.control_id }}</td></tr>
    {% endif %}
    <tr><td class="top_report_key">Registreringsdatum</td><td class="top_report_val">&lt;REGISTRATION_DATE&gt;</td></tr>
    <tr><td class="top_report_key">Provtyp</td><td class="top_report_val">&lt;TUMOR_SAMPLE_TYPE&gt;</td></tr>
    {% if assay_group not in ["swea", "gmsonco"] %}
    <tr>
      <td class="top_report_key">Frågeställning</td>
      <td class="top_report_val">
        {% if assay_group in ["myeloid", "hematology"] %}
          {% if sample.sample_no == 2 %}Hematologisk neoplasi{% else %}&lt;DIAGNOSIS&gt;{% endif %}
        {% elif assay_group == "solid" %}
          {% if sample.subpanel %}{% if sample.subpanel == "BP" %}Bröst-Pilot{% else %}{{ sample.subpanel }}{% endif %}{% endif %}
        {% endif %}
      </td>
    </tr>
    {% endif %}
    <tr><td class="top_report_key">Rapportdatum</td><td class="top_report_val">{{ report_date }}</td></tr>
    <tr><td class="top_report_key">Analysmetod</td><td class="top_report_val">{{ assay_config.reporting.report_method }}</td></tr>
    <tr><td class="top_report_key">Analys genomförd av</td><td class="top_report_val">Centrum för molekylär diagnostik (CMD) och Klinisk genetik och patologi</td></tr>
    <tr><td class="top_report_key">Rapport genererad av</td><td class="top_report_val">{{ current_user.fullname }}</td></tr>
    <tr>
      {% set report_name = sample.get("case_id", "NONE") + "_" + sample.get("case", {}).get("clarity_id", "NONE") %}
      {% if sample.control_id %}
        {% set report_name = report_name + "-" + sample.get("control_id", "NONE") + "_" + sample.get("control",{}).get("clarity_id", "NONE") %}
      {% endif %}
      <td class="top_report_key">Rapportnummer</td>
      <td class="top_report_val">{{ sample.report_num + 1 if sample.report_num is defined else 1 }}</td>
    </tr>
    <tr><td class="top_report_key">Rapport-ID</td><td class="top_report_val">{{ report_name }}.{{ report_timestamp }}</td></tr>
  </table>
</div>

<span class="report_header">Analysresultat</span>
{% if "SNV" in report_sections %}
  {% set variants = report_sections_data.snvs %}
  <span class="report_header">Kliniskt relevanta SNVs och små INDELs</span>
  <table class="variant_table">
    <tr><th>Gen</th><th>Mutation</th><th>Variantfrekvens</th><th>Klassificering</th></tr>
    {% for var in variants %}
      <tr>
        <td>{{ var.symbol }}</td>
        <td>{% if var.indel_size > 20 %}{{ var.cdna }}{% else %}{{ var.variant|unesc }}{% endif %}</td>
        <td>{{ var.af|perc_no_dec }}</td>
        <td>{{ var.class_short_desc }}</td>
      </tr>
    {% else %}
      <tr><td>Inga detekterade mutationer</td></tr>
    {% endfor %}
  </table>
{% endif %}

<p>Note: p = protein, c = cDNA, g = genomic</p>

{% if "CNV" in report_sections %}
  {% set cnvs = report_sections_data.cnvs %}
  <span class="report_header">Kliniskt relevanta kopietalsförändringar</span>
  <table class="variant_table">
    <tr><th>Gen(er)</th><th>Storlek</th><th>Typ</th><th>Kopietal</th></tr>
    {% for cnv in cnvs %}
      <tr>
        <td>
          {% set non_panel_genes = [0] %}
          {% for gene in cnv.genes %}
            {% if gene.class %}{{ gene.gene }}{% else %}{% if non_panel_genes.append(non_panel_genes.pop()+1) %}{% endif %}{% endif %}
          {% endfor %}
          {% if non_panel_genes[0] > 0 %}<font color='#888'>+ {{ non_panel_genes[0] }} other genes</font>{% endif %}
        </td>
        <td>{{ cnv.size }} bp</td>
        <td>{% if cnv.ratio > 1 %}AMP{% elif cnv.ratio > 0 %}DUP{% else %}DEL{% endif %}</td>
        <td>{{ 2*(2**cnv.ratio)|round(2) }}</td>
      </tr>
    {% else %}
      <tr><td>Inga detekterade kopietalsförändringar.</td></tr>
    {% endfor %}
  </table>
{% endif %}

{% if "TRANSLOCATION" in report_sections %}
  {% set translocs = report_sections_data.translocs %}
  <span class="report_header">Kliniskt relevanta fusioner (DNA)</span>
  <table class="variant_table">
    <tr><th>Gen 1</th><th>Gen 2</th><th>HGVS.p</th></tr>
    {% for tl in translocs %}
      {% set sel_ann = tl.INFO.MANE_ANN or tl.INFO.ANN[0] %}
      {% set genes = sel_ann.Gene_Name.split('&') %}
      <tr><td>{{ genes[0] }}</td><td>{{ genes[1] }}</td><td>{{ sel_ann.HGVSp|unesc }}</td></tr>
    {% else %}
      <tr><td>Inga detekterade fusioner</td></tr>
    {% endfor %}
  </table>
{% endif %}

<span class="report_header">Slutsats</span>
<div class="conclusion">
  <div class="results_summary">
    {% if sample.comments|length > 0 %}
      {% for comment in sample.comments if comment.hidden != 1 %}
        {% if loop.last %}{{ comment.text|format_comment|safe }}{% endif %}
      {% endfor %}
    {% else %}
      Slutsats saknas!
    {% endif %}
  </div>
</div>

<p style="page-break-before: always;"></p>
<br>

{% if report_sections_data.get('cnv_profile_base64') %}
  <span class="report_header">Kopietalsprofil, genomisk översikt</span>
  <div style="transform:rotate(90deg);">
    <img style="width:900px; height:auto; padding:30px;" src="data:image/png;base64,{{ report_sections_data.cnv_profile_base64 }}">
  </div>
  <p style="page-break-after: always;"></p>
{% endif %}

{% if variants %}
  <span class="report_header">Detekterade mutationer</span>
  {% for var in variants %}
    <div class=report_div style="page-break-inside:avoid;">
      <table class='report_variant'>
        <tr>
          <th class="report_variant_header" colspan=6>
            {% if var.variant %}
              <span class="report_variant_header">{{ var.symbol }}:
                {% if var.variant|unesc|length < 30 %}{{ var.variant|unesc }}</span><br>{% else %}{{ var.cdna }}{% endif %}
            {% endif %}
          </th>
        </tr>
        <tr>
          <td class="report_key">Gen</td><td class="var_report_val">{{ var.symbol }}</td>
          <td class="report_key">Typ</td><td class="var_report_val">{{ var.class_type }} {{ var.variant_class }}</td>
          <td class="report_key">Transkript</td><td class="var_report_val">{{ var.feature }}{% if var.exon %}, exon {{ var.exon[0] }}{% elif var.intron %}, intron {{ var.intron[0] }}{% endif %}</td>
        </tr>
        <tr>
          <td class="report_key">Konsekvens</td><td class="var_report_val">{{ var.consequence }}</td>
          <td class="report_key">cDNA-förändring</td>
          {% if var.var_type == "snv" %}<td class="var_report_val"><div class="wrapping">{{ var.cdna|unesc }}</div></td>{% else %}<td class="var_report_val">{{ var.cdna }}</td>{% endif %}
          <td class="report_key">Proteinförändring</td>
          <td class="var_report_val">
            {% if var.indel_size < 20 %}
              {% if var.protein_changes %}{% for p_change in var.protein_changes %}{{ p_change|safe }}<br>{% endfor %}{% endif %}
            {% else %}
              {{ var.cdna }}
            {% endif %}
          </td>
        </tr>
        <tr>
          <td class="report_key">Kromosom</td><td class="var_report_val">chr{{ var.chr }}</td>
          <td class="report_key">Position (hg38)</td><td class="var_report_val">{{ var.pos }}</td>
          <td class="report_key">Frekvens</td><td class="var_report_val">{{ var.af|perc_no_dec }}</td>
        </tr>
        {% if var.class != 999 %}
          <tr><td class="report_key">Klassificering</td><td class="report_annotation" colspan=5>{{ var.class|format_tier }} - {{ var.class_long_desc }}<br></td></tr>
        {% endif %}
        {% if var.global_annotations|length > 0 %}
          <tr>
            <td class="report_key">Kommentar</td>
            {% if var.annotations_interesting|length > 0 %}
              {% for assay_sub, key in var.annotations_interesting.items() %}
                <td class="report_annotation" colspan=5>{{ key.text|format_comment|safe }}</td>
              {% endfor %}
            {% else %}
              {% set sorted_annos = var.global_annotations|sort(attribute="time_created", reverse=True) %}
              <td class="report_annotation" colspan=5>{{ sorted_annos[0].text|format_comment|safe }}</td>
            {% endif %}
          </tr>
        {% endif %}
      </table>
    </div>
  {% endfor %}
{% endif %}

<span class="report_header">Analysbeskrivning</span>
<div class="analysis_description">
  {{ assay_config.reporting.report_description|safe }}

  {% set ns = namespace(table_no=1) %}
  <div>
    {% for genelist_name, genelist_values in genes_covered_in_panel.items() %}
      {% if genelist_name != sample.assay %}
        <p><b>Tabell {{ ns.table_no }}: Gener inkluderade i <i>{{ genelist_name }}</i> insilico-panel</b></p>
        <div>
          <table class="genetable" id="snvs-table">
            <tbody>
              {% for i in range(0, genelist_values.covered | length, 15) %}
                <tr>
                  {% for gene in genelist_values.covered[i:i+15] %}<td>{{ gene }}</td>{% endfor %}
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        {% set ns.table_no = ns.table_no + 1 %}
      {% endif %}
    {% endfor %}
  </div>

  {% if not germline %}
    <p><b>Tabell {{ ns.table_no }}: Förklaring av klassificering</b></p>
    <table class="info">
      <tr><td>Tier I</td><td>Variant av stark klinisk signifikans (genmutationer som är diagnostiska, behandlingsstyrande eller riskstratifierande enligt gällande riktlinjer)</td></tr>
      <tr><td>Tier II</td><td>Variant av potentiell klinisk signifikans (mutationer i gener beskrivna i ett flertal publikationer)</td></tr>
      <tr><td>Tier III</td><td>Variant av oklar klinisk signifikans (mutationer i gener beskrivna i ett fåtal publikationer)</td></tr>
      <tr><td>Tier IV</td><td>Variant bedömd som benign eller sannolikt benign</td></tr>
    </table>
    <p><b>Referenser</b></p>
    <p>[1] Standards and guidelines for the interpretation and reporting of sequence variants in cancer. Li et al, Journal of Molecular Diagnostics, 2017.</p>
  {% endif %}
</div>

{% endblock %}
"""


RNA_REPORT_TEMPLATE = r"""{% extends "report_layout.html" %}
{% block title %}RNA Report{% endblock %}
{% block body %}

{% if pdf != 1 %}
<div class="report-preview-card">
  <h2 class="report-heading">*** PREVIEW OF REPORT ***</h2>
  <b>*** PREVIEW OF REPORT ***</b><br><br>
</div>
{% endif %}

<span class="report_header">{{ report_header }} - {{ sample.name }}</span>

<div class="report_div">
  <table class='report_general'>
    <tr><td class="top_report_key">Patientnamn</td><td class="top_report_val">&lt;PATIENT_NAME&gt;</td></tr>
    <tr><td class="top_report_key">Personnummer</td><td class="top_report_val">&lt;PERSONAL_IDENTITY_NUMBER&gt;</td></tr>
    <tr><td class="top_report_key">Prov-ID</td><td class="top_report_val">{{ sample.name }}</td></tr>
    <tr><td class="top_report_key">Registreringsdatum</td><td class="top_report_val">&lt;REGISTRATION_DATE&gt;</td></tr>
    <tr><td class="top_report_key">Provtyp</td><td class="top_report_val">&lt;SAMPLE_TYPE&gt; / RNA</td></tr>
    <tr><td class="top_report_key">Frågeställning</td><td class="top_report_val">{% if assay == "fusions" %}RNA fusions{% else %}Gene Panel{% endif %}</td></tr>
    <tr><td class="top_report_key">Rapportdatum</td><td class="top_report_val">{{ report_date }}</td></tr>
    <tr><td class="top_report_key">Analysmetod</td><td class="top_report_val">{{ analysis_method }}</td></tr>
    <tr><td class="top_report_key">Analys genomförd av</td><td class="top_report_val">Centrum för molekylär diagnostik (CMD) och Klinisk genetik och patologi</td></tr>
    <tr><td class="top_report_key">Rapport genererad av</td><td class="top_report_val">{{ current_user.fullname }}</td></tr>
    <tr><td class="top_report_key">Rapport-ID</td><td class="top_report_val">{{ sample.name }}.{{ sample.report_num + 1 if sample.report_num is defined else 1 }}</td></tr>
  </table>
</div>

<span class="report_header">Analysresultat</span>
<table class="variant_table">
  {% if assay=="fusion" %}<tr><th>Fusion</th><th>Klassificering</th></tr>{% elif assay=="fusionrna" %}<tr><th>Fusion/exon skipping</th><th>Klassificering</th></tr>{% endif %}
  {% for var in fusions|sort(attribute='classification.class') if (not var.blacklist and var.classification.class != 999 and var.classification.class != 4) %}
    <tr><td>{{ var.gene1 }} - {{ var.gene2 }}</td><td>{{ class_desc_short[var.classification.class] }}</td></tr>
  {% else %}
    <tr><td>Inga detekterade fusioner</td><td></td></tr>
  {% endfor %}
</table>

<span class="report_header">Slutsats</span>
<div class="conclusion">
  <div class="results_summary">
    {% if sample.comments|length > 0 %}
      {% for comment in sample.comments if comment.hidden != 1 %}
        {% if loop.last %}{{ comment.text|format_comment|safe }}{% endif %}
      {% endfor %}
    {% else %}
      Slutsats saknas!
    {% endif %}
  </div>
</div>

<p style="page-break-before: always;"></p>
<br>

{% if assay=="fusion" %}<span class="report_header">Detekterade fusioner</span>{% elif assay=="fusionrna" %}<span class="report_header">Detekterade fusioner och exon skipping</span>{% endif %}
{% for var in fusions|sort(attribute='classification.class') if not var.blacklist and var.classification.class != 999 and var.classification.class != 4 %}
  {% set selected_calls = var.calls|selectattr('selected', 'equalto', 1)|list %}
  {% set sel_fus = selected_calls[0] if selected_calls else var.calls[0] %}
  <div class=report_div style="page-break-inside:avoid;">
    <table class='report_variant'>
      <tr><th class="report_variant_header" colspan=6>{{ var.gene1 }} - {{ var.gene2 }}</th></tr>
      <tr>
        <td class="report_key">Gener</td><td class="var_report_val">{{ var.gene1 }} - {{ var.gene2 }}</td>
        <td class="report_key">Effekt</td><td class="var_report_val">{% if sel_fus.spanpairs|int > 0 %}{{ sel_fus.effect }}{% else %}NA{% endif %}</td>
        <td class="report_key">Fusionspunkter</td><td class="var_report_val">{% if sel_fus.spanpairs|int > 0 %}{{ sel_fus.breakpoint1 }} {{ sel_fus.breakpoint2 }}{% else %}NA{% endif %}</td>
      </tr>
      <tr>
        <td class="report_key">Antal läsningar</td><td class="var_report_val">{{ sel_fus.spanreads }}</td>
        <td class="report_key">Antal läs-par</td><td class="var_report_val">{{ sel_fus.spanpairs }}</td>
        <td class="report_key">Längsta ankarsekvens</td><td class="var_report_val">{% if sel_fus.longestanchor %}{{ sel_fus.longestanchor }} bp{% else %}NA{% endif %}</td>
      </tr>
      {% if var.classification.class != 999 %}
        <tr><td class="report_key">Klassificering</td><td class="report_annotation" colspan=5>{{ var.classification.class|format_tier }} - {{ class_desc[var.classification.class] }}<br></td></tr>
      {% endif %}
      {% if var.global_annotations|length > 0 %}
        <tr><td class="report_key">Kommentar</td>{% set sorted_annos = var.global_annotations|sort(attribute="time_created", reverse=True) %}<td class="report_annotation" colspan=5>{{ sorted_annos[0].text|format_comment|safe }}</td></tr>
      {% endif %}
    </table>
  </div>
{% else %}
  <tr><td>Inga detekterade fusioner</td><td></td></tr>
{% endfor %}

<span class="report_header">Analysbeskrivning</span>
<div class="analysis_description">
  {{ analysis_desc|safe }}
  <p><b>Tabell: Förklaring av klassificering</b></p>
  <table class="info">
    <tr><td>Tier I</td><td>Variant av stark klinisk signifikans (innefattar varianter i gener som finns med i internationella/nationella riktlinjer)</td></tr>
    <tr><td>Tier II</td><td>Variant av potentiell klinisk signifikans (innefattar varianter i gener som finns med i publikationer)</td></tr>
    <tr><td>Tier III</td><td>Variant av oklar klinisk signifikans (innefattar varianter i gener i få eller inga publikationer)</td></tr>
    <tr><td>Tier IV</td><td>Variant bedömd som benign eller sannolikt benign</td></tr>
  </table>
  <p><b>Referenser</b></p>
  <p>[1] Standards and guidelines for the interpretation and reporting of sequence variants in cancer. Li et al, Journal of Molecular Diagnostics, 2017.</p>
</div>

{% endblock %}
"""


def _environment() -> Environment:
    """Return the report Jinja environment with Coyote3 report filters."""
    env = Environment(
        loader=DictLoader(
            {
                "report_layout.html": REPORT_LAYOUT_TEMPLATE,
                "dna_report.html": DNA_REPORT_TEMPLATE,
                "report_fusion.html": RNA_REPORT_TEMPLATE,
            }
        ),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["perc_no_dec"] = _perc_no_dec
    env.filters["unesc"] = _unesc
    env.filters["format_comment"] = _format_comment
    env.filters["format_tier"] = _format_tier
    return env


def _perc_no_dec(value: Any) -> str:
    """Format allele frequency for clinical report display."""
    if value in (None, "", "N/A"):
        return "N/A" if value == "N/A" else "-"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _unesc(value: Any) -> str:
    """Return a text value without HTML escaping entities twice."""
    return str(value or "")


def _format_tier(value: Any) -> str:
    """Format a numeric tier using clinical report wording."""
    try:
        return f"Tier {TIER_NAME.get(int(value), int(value))}"
    except (TypeError, ValueError):
        return str(value or "-")


def _format_comment(value: Any) -> str:
    """Render markdown comments safely for report output."""
    text = str(value or "")
    html = markdown.markdown(text, extensions=["extra", "sane_lists"])
    return bleach.clean(
        html,
        tags=[
            "p",
            "br",
            "strong",
            "em",
            "b",
            "i",
            "ul",
            "ol",
            "li",
            "code",
            "pre",
            "blockquote",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ],
        attributes={"a": ["href", "title"]},
        strip=True,
    )


def _clinical_report_user() -> SimpleNamespace:
    """Return the default user context for server-rendered clinical reports."""
    return SimpleNamespace(fullname="Coyote3", get_fullname=lambda: "Coyote3")


def _clinical_report_request() -> SimpleNamespace:
    """Return the default request context for server-rendered clinical reports."""
    return SimpleNamespace(script_root="")


def _template_defaults(context: dict[str, Any], *, analyte: str, preview: bool) -> dict[str, Any]:
    """Add clinical report globals and missing optional fields."""
    sample = dict(context.get("sample") or {})
    sample.setdefault("comments", [])
    sample.setdefault("report_num", 0)
    context = dict(context)
    context["sample"] = sample
    context.setdefault("current_user", _clinical_report_user())
    context.setdefault("request", _clinical_report_request())
    context.setdefault("has_access", lambda *_args, **_kwargs: False)
    context.setdefault("url_for", lambda endpoint, **_kwargs: f"#{endpoint}")
    context.setdefault("germline", False)
    context.setdefault("pdf", 0 if preview else 1)
    context["save"] = 0 if preview else 1
    if analyte == "rna":
        context.setdefault("assay", context.get("assay") or "fusion")
    return context


def render_report_html(
    *,
    template_name: str,
    template_context: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    analyte: str,
    preview: bool,
) -> str:
    """Render report HTML from the canonical workflow context."""
    _ = snapshot_rows
    context = _template_defaults(template_context, analyte=analyte, preview=preview)
    selected_template = "report_fusion.html" if analyte == "rna" else "dna_report.html"
    if template_name in {"dna_report.html", "report_fusion.html"}:
        selected_template = template_name
    return _environment().get_template(selected_template).render(**context)


def render_pdf_bytes(html: str) -> bytes:
    """Render a PDF byte stream from report HTML."""
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
