"""DNA export row builders and shared normalization helpers."""

from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Any

from api.contracts.dna import DnaCnvExportRow, DnaSnvExportRow, DnaTranslocExportRow
from api.core.dna.notation import one_letter_p


def consequence_terms(value: object) -> set[str]:
    """Normalize selected_CSQ consequence values into a comparable term set."""
    if isinstance(value, str):
        terms = [part.strip() for part in value.split("&")]
        return {term for term in terms if term}
    if isinstance(value, (list, tuple, set)):
        normalized = set()
        for item in value:
            text = str(item).strip()
            if text:
                normalized.add(text)
        return normalized
    if value in {None, ""}:
        return set()
    text = str(value).strip()
    return {text} if text else set()


def consequence_list(value: object) -> list[str]:
    """Normalize selected_CSQ consequence values into list form."""
    if isinstance(value, str):
        return [part.strip() for part in value.split("&") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in {None, ""}:
        return []
    text = str(value).strip()
    return [text] if text else []


def join_tokens(value: object, *, delimiter: str = " | ") -> str:
    """Normalize arbitrary list/string-ish values as a single pipe-delimited string."""
    if value is None:
        return ""
    if isinstance(value, str):
        raw_tokens = []
        for split_value in value.replace("\r", "\n").split("\n"):
            raw_tokens.extend(split_value.split("&"))
            raw_tokens.extend(split_value.split(","))
            raw_tokens.extend(split_value.split(";"))
        tokens = [token.strip() for token in raw_tokens if token.strip()]
    elif isinstance(value, (list, tuple, set)):
        tokens = []
        for item in value:
            token = str(item).strip()
            if token:
                tokens.append(token)
    else:
        token = str(value).strip()
        tokens = [token] if token else []
    return delimiter.join(tokens)


def yes_no(value: object) -> str:
    """Return a stable yes/no string for truthy values."""
    return "yes" if bool(value) else "no"


def safe_text(value: object) -> str:
    """Normalize free text for compact CSV-friendly rendering."""
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def protect_excel(value: object) -> str:
    """Prevent Excel auto-conversion for date-like / number-like string values."""
    text = safe_text(value)
    if not text:
        return text
    risky = any(
        (
            re.match(r"^\d+\s*/\s*\d+$", text, flags=re.I),
            re.match(r"^\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?$", text),
            re.match(
                r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{1,4}$", text, flags=re.I
            ),
            re.match(r"^\d{15,}$", text),
            re.match(r"^0\d+$", text),
            re.match(r"^\d+:\d+(:\d+)?$", text),
            re.match(r"^\d+(\.\d+)?e[+-]?\d+$", text, flags=re.I),
        )
    )
    return f"'{text}" if risky else text


def export_rows_to_csv(
    rows: list[DnaSnvExportRow] | list[DnaCnvExportRow] | list[DnaTranslocExportRow],
) -> str:
    """Serialize typed export rows into CSV text with stable column ordering."""
    output = StringIO()
    if not rows:
        return ""
    headers = list(rows[0].model_dump().keys())
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        normalized: dict[str, str] = {}
        for key, value in row.model_dump().items():
            normalized[key] = protect_excel(value)
        writer.writerow(normalized)
    return output.getvalue()


def build_snv_export_rows(variants: list[dict[str, Any]]) -> list[DnaSnvExportRow]:
    """Build typed SNV export rows from filtered variant documents."""
    rows: list[DnaSnvExportRow] = []
    for var in variants:
        selected = var.get("INFO", {}).get("selected_CSQ", {})
        comments = var.get("comments") or []
        latest_comment = comments[-1] if comments else {}
        gt_values = var.get("GT") or []
        case_gt = []
        control_gt = []
        for gt in sorted(gt_values, key=lambda x: x.get("type", "")):
            try:
                gt_text = (
                    f"{100 * float(gt.get('AF', 0)):0.1f}% "
                    f"({int(gt.get('VD', 0))} / {int(gt.get('DP', 0))})"
                )
            except Exception:
                gt_text = safe_text(gt)
            if gt.get("type") == "case":
                case_gt.append(gt_text)
            else:
                control_gt.append(gt_text)

        classification = var.get("classification", {})
        tier_value = "-"
        if (
            classification
            and classification.get("class") != 999
            and classification.get("transcript") == selected.get("Feature")
        ):
            tier_value = str(classification.get("class"))
        elif var.get("additional_classification") and var["additional_classification"].get("tier"):
            tier_value = str(var["additional_classification"].get("tier"))
        elif var.get("other_classification"):
            tier_value = "?"

        consequence = join_tokens(selected.get("Consequence"))
        flags = join_tokens(var.get("FILTER"))
        blacklisted = bool(var.get("blacklist")) and not bool(var.get("override_blacklist"))
        indel_size_num = len(str(var.get("ALT", ""))) - len(str(var.get("REF", "")))
        if indel_size_num == 0:
            indel_size = "-"
        else:
            indel_suffix = "DEL" if indel_size_num < 0 else "INS"
            indel_size = f"{indel_size_num} bp {indel_suffix}"

        row = DnaSnvExportRow(
            gene=safe_text(selected.get("SYMBOL")),
            hgvsp=safe_text(one_letter_p(selected.get("HGVSp"))),
            hgvsc=safe_text(selected.get("HGVSc")),
            exon=safe_text(selected.get("EXON") or "-"),
            intron=safe_text(selected.get("INTRON") or "-"),
            var_type=safe_text(var.get("variant_class")),
            indel_size=indel_size,
            consequence=consequence,
            pop_freq=safe_text(var.get("gnomad_frequency") if var.get("gnomad_frequency") else "-"),
            tier=tier_value,
            chr_pos=f"{safe_text(var.get('CHROM'))}:{safe_text(var.get('POS'))}",
            flags=flags,
            case_gt=join_tokens(case_gt),
            control_gt=join_tokens(control_gt),
            false_positive=yes_no(var.get("fp")),
            irrelevant=yes_no(var.get("irrelevant")),
            interesting=yes_no(var.get("interesting")),
            blacklisted=yes_no(blacklisted),
            latest_comment=safe_text(latest_comment.get("text")),
            latest_comment_author=safe_text(latest_comment.get("author")),
            latest_comment_time=safe_text(latest_comment.get("time_created")),
        )
        rows.append(row)
    return rows


def build_cnv_export_rows(
    cnvs: list[dict[str, Any]],
    sample: dict[str, Any],
    assay_group: str,
) -> list[DnaCnvExportRow]:
    """Build typed CNV export rows from filtered CNV documents."""
    rows: list[DnaCnvExportRow] = []
    sample_purity = sample.get("purity")
    for cnv in cnvs:
        comments = cnv.get("comments") or []
        latest_comment = comments[-1] if comments else {}
        genes = []
        other_genes = 0
        for gene in cnv.get("genes", []):
            if gene.get("class"):
                genes.append(str(gene.get("gene", "")).strip())
            else:
                other_genes += 1
        genes_value = join_tokens(genes)
        if other_genes > 0:
            genes_value = (
                f"{genes_value} | + {other_genes} other genes"
                if genes_value
                else f"+ {other_genes} other genes"
            )

        callers_value = safe_text(cnv.get("callers", ""))
        ratio = cnv.get("ratio")
        copy_number_value = ""
        purity_cn_value = ""
        ref_alt_reads = "-"
        try:
            ratio_num = float(ratio)
            copy_number_value = f"{round(2 * (2**ratio_num), 2)} ({safe_text(ratio)})"
            if sample_purity not in {None, "", 0}:
                purity_float = float(sample_purity)
                if ratio_num > 0:
                    purity_cn_value = safe_text(round((2 * (2**ratio_num)) * 1 / purity_float, 2))
                else:
                    purity_cn_value = safe_text(round((2 * (2**ratio_num)) * purity_float, 2))
        except Exception:
            copy_number_value = safe_text(ratio)

        if assay_group in {"solid", "gmsonco"}:
            ref_alt_reads = safe_text(cnv.get("PR", "-") or "-")
            if "gatk" not in callers_value and "cnvkit" not in callers_value:
                copy_number_value = "-"

        status = ""
        if cnv.get("interesting"):
            status = "report"
        elif cnv.get("fp"):
            status = "false positive"
        elif cnv.get("noteworthy"):
            status = "noteworthy"

        artefact_items = []
        for key, value in cnv.items():
            if not str(key).startswith("AFRQ_"):
                continue
            label = str(key).split("_", 1)[1]
            try:
                percent = round(float(value) * 100, 1)
                count_value = cnv.get(f"ACOUNT_{label}")
                if count_value is not None:
                    artefact_items.append(f"{label}:{percent}% ({count_value})")
                else:
                    artefact_items.append(f"{label}:{percent}%")
            except Exception:
                continue

        row = DnaCnvExportRow(
            genes=genes_value,
            region=f"{safe_text(cnv.get('chr'))}:{safe_text(cnv.get('start'))}-{safe_text(cnv.get('end'))}",
            size_bp=safe_text(abs(int(cnv.get("size", 0))) if cnv.get("size") is not None else ""),
            callers=callers_value,
            copy_number=copy_number_value,
            purity_copy_number=purity_cn_value,
            ref_alt_reads=ref_alt_reads,
            status=status,
            artefact=join_tokens(artefact_items),
            false_positive=yes_no(cnv.get("fp")),
            irrelevant=yes_no(cnv.get("irrelevant")),
            interesting=yes_no(cnv.get("interesting")),
            latest_comment=safe_text(latest_comment.get("text")),
            latest_comment_author=safe_text(latest_comment.get("author")),
            latest_comment_time=safe_text(latest_comment.get("time_created")),
        )
        rows.append(row)
    return rows


def build_transloc_export_rows(translocs: list[dict[str, Any]]) -> list[DnaTranslocExportRow]:
    """Build typed translocation export rows from filtered translocation documents."""
    rows: list[DnaTranslocExportRow] = []
    for tl in translocs:
        info = tl.get("INFO", {})
        ann = info.get("MANE_ANN") or (info.get("ANN") or [{}])[0]
        gene_names = str(ann.get("Gene_Name", "")).split("&")
        gene_1 = safe_text(gene_names[0] if len(gene_names) > 0 else "")
        gene_2 = safe_text(gene_names[1] if len(gene_names) > 1 else "")
        annotations = ann.get("Annotation") or []
        comments = tl.get("comments") or []
        latest_comment = comments[-1] if comments else {}
        status = "report" if tl.get("interesting") else ""

        row = DnaTranslocExportRow(
            gene_1=gene_1,
            gene_2=gene_2,
            positions=f"{safe_text(tl.get('CHROM'))}:{safe_text(tl.get('POS'))} {safe_text(tl.get('ALT'))}",
            var_type=join_tokens(annotations),
            hgvsp=safe_text(one_letter_p(ann.get("HGVSp"))),
            hgvsc=safe_text(ann.get("HGVSc")),
            panel=safe_text(info.get("PANEL")),
            status=status,
            false_positive=yes_no(tl.get("fp")),
            interesting=yes_no(tl.get("interesting")),
            latest_comment=safe_text(latest_comment.get("text")),
            latest_comment_author=safe_text(latest_comment.get("author")),
            latest_comment_time=safe_text(latest_comment.get("time_created")),
        )
        rows.append(row)
    return rows
