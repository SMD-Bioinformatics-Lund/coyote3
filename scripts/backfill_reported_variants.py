#!/usr/bin/env python3
"""
backfill_reported_variants.py

Enhancements:
- Process subset of samples by --sample-names "name1,name2"
- Output JSONL files first:
    * <out-prefix>.success.jsonl  (ready-to-insert docs)
    * <out-prefix>.errors.jsonl   (unmatched variants / failures with context)
- Output Log File:
    * <out-prefix>.log
- Optional DB insert after producing JSONL: --insert
- Optional bulk insert from an external JSONL file: --from-json path/to/file.jsonl

MongoDB 3.4 compatible.

Example Commands

python backfill_reported_variants.py \
  --mongo-uri "mongodb://..." --db coyote3 \
  --sample-names "25MD17060p-2,25MD17061p-1" \
  --out-prefix /tmp/reported_variants_subset \
  --dry-run --verbose

python backfill_reported_variants.py \
  --mongo-uri "mongodb://..." --db coyote3 \
  --sample-names "25MD17060p-2,25MD17061p-1" \
  --out-prefix /tmp/reported_variants_subset \
  --insert --verbose

python backfill_reported_variants.py \
  --mongo-uri "mongodb://..." --db coyote3 \
  --from-json /tmp/reported_variants_subset.success.jsonl

Instructions
{
        "_id" : ObjectId("6978dfc2aac5ed89b2f935d4"),
        "report_oid" : ObjectId("6978dfc286f3bbbcff2b9a29"), # get from sample.reports (samples collection)
        "sample_oid" : ObjectId("696fba905d3ec4f921bc297d"), # sample.oid (samples collection)
        "simple_id" : "12_6593408_T_G", # get from variants.simple_id # linked by sample._id == variant.SAMPLE_ID
        "sample_name" : "25MD17060p-2", # sample.name
        "report_id" : "25MD17060_GEN1202A4951-25MD17062_GEN1202A5038.260127155435", sample.reports.[$].report_id
        "created_by" : "ram.nanduri", # sample.reports.[$].author
        "var_oid" : ObjectId("696fba905d3ec4f921bc2c88"),  # get from variants._id # linked by sample._id == variant.SAMPLE_ID
        "annotation_oid" : ObjectId("6966b93df862280694f29748"), # find the latest annotation based variant(remove paranthesis) + class(tier) + assay + subpanel(if available or assay alone) from annotaiton collection, the latest annotation should not be greater than the report date
        "annotation_text_oid" : null, # find the latest annotation text not the class docs based variant(remove paranthesis) + assay + subpanel(if available or assay alone) from annotaiton collection, the latest annotation should not be greater than the report date
        "sample_comment_oid" : ObjectId("69722f9f05e835b679cf700d"), # latest sample.comments whose date is not grater than report date
        "var_type" : "SNV", # get from variants.variant_class # linked by sample._id == variant.SAMPLE_ID
        "simple_id_hash" : null, # get from variants.simple_id_hash or null  # linked by sample._id == variant.SAMPLE_ID
        "tier" : 3, # class/tier from the variant extracted from the report, should also match the annotation selected annotation_oid
        "gene" : "CHD4", # get from variants.INFO.selected_CSQ.SYMBOL
        "transcript" : "NM_001273.5", # get from variants.INFO.selected_CSQ.Feature
        "hgvsp" : null, # get from variants.INFO.selected_CSQ.HGVSp
        "hgvsc" : "c.2514+8A>C", # get from variants.INFO.selected_CSQ.HGVSc
        "variant" : "c.2514+8A>C", # variant extracted from the report after removing paranthesis
        "created_on" : ISODate("2026-01-27T15:54:42.813Z") # report date
}

"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import logging
import socket
import getpass
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError


# ---------------------------- Constants ----------------------------
TIER_NAME_TO_INT = {
    "None": 0,
    "Stark klinisk signifikans": 1,
    "Potentiell klinisk signifikans": 2,
    "Oklar klinisk signifikans": 3,
    "Benign/sannolikt benign": 4,
}

ASSAY_MAP = {
    "hema_GMSv1": "hematology",
    "solid_GMSv3": "solid",
    "tumwgs": "tumwgs",
    "tumwgs_hema": "tumwgs",
    "tumwgs_solid": "tumwgs",
    "myeloid_GMSv1": "myeloid",
}


ONE_TO_THREE = {
    "A": "Ala",
    "R": "Arg",
    "N": "Asn",
    "D": "Asp",
    "C": "Cys",
    "Q": "Gln",
    "E": "Glu",
    "G": "Gly",
    "H": "His",
    "I": "Ile",
    "L": "Leu",
    "K": "Lys",
    "M": "Met",
    "F": "Phe",
    "P": "Pro",
    "S": "Ser",
    "T": "Thr",
    "W": "Trp",
    "Y": "Tyr",
    "V": "Val",
    "*": "Ter",
}

PROTEIN_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)([A-Za-z\*]{1,3}|=)\)?$")

# p.Y2285Tfs*5  or p.(Y2285Tfs*5)  or already three-letter p.Tyr2285ThrfsTer5
FS_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)([A-Za-z\*]{1,3})fs(?:\*|Ter)?(\d+)\)?$")

# p.A142_E143insV   or p.(A142_E143insV)
# also supports 3-letter like p.Ala142_Glu143insVal
INS_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)ins([A-Za-z\*]{1,3})\)?$")

# p.P95_R102del   or p.(P95_R102del)
# also supports 3-letter like p.Pro95_Arg102del
DEL_RANGE_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)del\)?$")

# p.M1? or p.(M1?) or already three-letter p.Met1?
UNCERTAIN_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)\?\)?$")

# p.V92_P96dup   or p.(V92_P96dup)
# also supports 3-letter: p.Val92_Pro96dup
DUP_RANGE_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)dup\)?$")

# Range delins: p.A37_A38delinsTP  / p.Ser433_Glu434delinsPWV
DELINS_RANGE_RE = re.compile(
    r"^p\.\(?([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)delins([A-Za-z\*]+)\)?$"
)

# Range ins: p.I639_Q670insHSR... / p.Ser433_Glu434insPWV
INS_RANGE_SEQ_RE = re.compile(
    r"^p\.\(?([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)ins([A-Za-z\*]+)\)?$"
)

# Equality (uncertain change marker): p.M1= / p.Met1=
EQUAL_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)=\)?$")

# Single-position delins with sequence: p.K948delinsA*
DELINS_SINGLE_RE = re.compile(r"^p\.\(?([A-Za-z\*]{1,3})(\d+)delins([A-Za-z\*]+)\)?$")


# ----------------------------- Logging -----------------------------


def setup_logger(log_path: str, verbose: bool) -> logging.Logger:
    """
    Create a logger that always logs to file, and optionally to stdout.
    """
    logger = logging.getLogger("reported_variants_backfill")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # prevent duplicate logs

    # Avoid duplicate handlers if main() is called twice
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (always enabled)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler (only if verbose)
    if verbose:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


# ----------------------------- Helpers -----------------------------


def parse_tier(value: str) -> Optional[int]:
    if not value:
        return None
    v = value.strip()
    if v.isdigit():
        return int(v)
    return TIER_NAME_TO_INT.get(v)


def normalize_hgvsp_three_letter(hgvsp: str) -> str:
    """
    Normalize protein HGVS to three-letter amino acids (best-effort), matching the
    formats seen in your HTML reports.

    Supports:
      - Substitution / stop / "=":
          p.(Q1034*)        -> p.Gln1034Ter
          p.(G62R)          -> p.Gly62Arg
          p.His763=         -> p.His763=
          p.H763=           -> p.His763=
      - Frameshift:
          p.Y2285Tfs*5      -> p.Tyr2285ThrfsTer5
          p.(Y2285TfsTer5)  -> p.Tyr2285ThrfsTer5
      - Range insertion (with inserted AA sequence, including long strings):
          p.Ser433_Glu434insPWV -> p.Ser433_Glu434insProTrpVal
          p.I639_Q670insHSR...  -> p.Ile639_Gln670insHisSerArg...
      - Range deletion:
          p.P95_R102del     -> p.Pro95_Arg102del
      - Range duplication:
          p.V92_P96dup      -> p.Val92_Pro96dup
      - Range delins (with inserted AA sequence):
          p.A37_A38delinsTP -> p.Ala37_Ala38delinsThrPro
          p.E1501_Y1503delinsD -> p.Glu1501_Tyr1503delinsAsp
      - Single-position delins (with inserted AA sequence):
          p.K948delinsA*    -> p.Lys948delinsAlaTer
      - Uncertain:
          p.M1?             -> p.Met1?

    Notes:
      - The report often uses one-letter amino acids; Mongo variants store three-letter.
      - This function converts one-letter AA sequences (including long insertions) into
        concatenated three-letter tokens, e.g. "DYV" -> "AspTyrVal", "*" -> "Ter".
      - If a pattern is not recognized, returns a cleaned best-effort string.

    Args:
        hgvsp: Protein HGVS string from report (may include parentheses).

    Returns:
        Normalized HGVS protein string using three-letter amino acids when possible.
    """
    if not hgvsp:
        return ""

    # Strip outer parentheses characters commonly present in report (p.(...))
    s = hgvsp.strip().replace("(", "").replace(")", "")

    # --- Local helpers ---
    def to_three(aa: str) -> str:
        # Already 3-letter (e.g., Arg)
        if len(aa) == 3 and aa[0].isalpha() and aa[1:].islower():
            return aa
        return ONE_TO_THREE.get(aa, aa)

    def seq_to_three(seq: str) -> str:
        """
        Convert one-letter AA sequence into concatenated three-letter tokens.
          "TP" -> "ThrPro"
          "A*" -> "AlaTer"
          "DYVDF" -> "AspTyrValAspPhe"
        If it isn't purely one-letter codes (plus '*'), return as-is.
        """
        if not seq:
            return seq
        if all(c in ONE_TO_THREE for c in seq):
            return "".join(ONE_TO_THREE[c] for c in seq)
        return seq

    # --- Regexes (compiled here for "complete function" convenience) ---
    PROTEIN_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)([A-Za-z\*]{1,3}|=)$")
    FS_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)([A-Za-z\*]{1,3})fs(?:\*|Ter)?(\d+)$")
    INS_RANGE_SEQ_RE_LOCAL = re.compile(
        r"^p\.([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)ins([A-Za-z\*]+)$"
    )
    DELINS_RANGE_RE_LOCAL = re.compile(
        r"^p\.([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)delins([A-Za-z\*]+)$"
    )
    DELINS_SINGLE_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)delins([A-Za-z\*]+)$")
    DEL_RANGE_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)del$")
    DUP_RANGE_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)_([A-Za-z\*]{1,3})(\d+)dup$")
    UNCERTAIN_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)\?$")
    EQUAL_RE_LOCAL = re.compile(r"^p\.([A-Za-z\*]{1,3})(\d+)=$")

    # --- Frameshift: p.Y2285Tfs*5 -> p.Tyr2285ThrfsTer5 ---
    m = FS_RE_LOCAL.match(s)
    if m:
        aa1, pos, aa2, stop_n = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"p.{to_three(aa1)}{pos}{to_three(aa2)}fsTer{stop_n}"

    # --- Range delins: p.A37_A38delinsTP ---
    m = DELINS_RANGE_RE_LOCAL.match(s)
    if m:
        aa1, pos1, aa2, pos2, ins_seq = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        return f"p.{to_three(aa1)}{pos1}_{to_three(aa2)}{pos2}delins{seq_to_three(ins_seq)}"

    # --- Range insertion with sequence: p.Ser433_Glu434insPWV / long strings ---
    m = INS_RANGE_SEQ_RE_LOCAL.match(s)
    if m:
        aa1, pos1, aa2, pos2, ins_seq = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        return f"p.{to_three(aa1)}{pos1}_{to_three(aa2)}{pos2}ins{seq_to_three(ins_seq)}"

    # --- Single-position delins: p.K948delinsA* ---
    m = DELINS_SINGLE_RE_LOCAL.match(s)
    if m:
        aa1, pos, ins_seq = m.group(1), m.group(2), m.group(3)
        return f"p.{to_three(aa1)}{pos}delins{seq_to_three(ins_seq)}"

    # --- Range deletion: p.P95_R102del ---
    m = DEL_RANGE_RE_LOCAL.match(s)
    if m:
        aa1, pos1, aa2, pos2 = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"p.{to_three(aa1)}{pos1}_{to_three(aa2)}{pos2}del"

    # --- Range duplication: p.V92_P96dup ---
    m = DUP_RANGE_RE_LOCAL.match(s)
    if m:
        aa1, pos1, aa2, pos2 = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"p.{to_three(aa1)}{pos1}_{to_three(aa2)}{pos2}dup"

    # --- Uncertain: p.M1? ---
    m = UNCERTAIN_RE_LOCAL.match(s)
    if m:
        aa1, pos = m.group(1), m.group(2)
        return f"p.{to_three(aa1)}{pos}?"

    # --- Equality: p.His763= / p.H763= ---
    m = EQUAL_RE_LOCAL.match(s)
    if m:
        aa1, pos = m.group(1), m.group(2)
        return f"p.{to_three(aa1)}{pos}="

    # --- Simple substitution/stop/"=": p.G62R, p.Q1034*, p.A123= ---
    m = PROTEIN_RE_LOCAL.match(s)
    if not m:
        return s  # unrecognized; best-effort cleaned form

    aa1, pos, aa2 = m.group(1), m.group(2), m.group(3)
    aa1_3 = to_three(aa1)

    if aa2 == "=":
        aa2_3 = "="
    else:
        aa2_3 = to_three(aa2)

    return f"p.{aa1_3}{pos}{aa2_3}"


def map_sample_assay_to_annotation_assay(sample_assay: Optional[str]) -> Optional[str]:
    """
    Map technical/pipeline assay names to annotation assay domain.

    Examples:
      hema_GMSv1     -> hematology
      solid_GMSv3    -> solid
      tumwgs_hema    -> tumwgs
    """
    if not sample_assay:
        return None

    return ASSAY_MAP.get(sample_assay, sample_assay)


def normalize_variant_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"^\((.*)\)$", r"\1", s)
    s = s.replace("(", "").replace(")", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def safe_get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def parse_iso_dt(x: Any) -> Optional[dt.datetime]:
    if isinstance(x, dt.datetime):
        return x
    return None


class JSONEncoder(json.JSONEncoder):
    """Make ObjectId + datetime JSON serializable."""

    def default(self, o):
        if isinstance(o, ObjectId):
            return {"$oid": str(o)}
        if isinstance(o, dt.datetime):
            return {"$date": o.isoformat()}
        return super().default(o)


def json_sanitize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId/datetime in-place into extended JSON objects."""
    # easiest: round-trip via JSONEncoder
    return json.loads(json.dumps(doc, cls=JSONEncoder))


def write_jsonl(path: str, docs: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(json_sanitize(d), ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def extjson_to_native(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert {"$oid": "..."} and {"$date": "..."} back to ObjectId/datetime.
    This supports the format produced by json_sanitize().
    """

    def conv(x):
        if isinstance(x, dict):
            if "$oid" in x and len(x) == 1:
                return ObjectId(x["$oid"])
            if "$date" in x and len(x) == 1:
                # isoformat parse (supports timezone too)
                return dt.datetime.fromisoformat(x["$date"])
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, list):
            return [conv(v) for v in x]
        return x

    return conv(doc)


# ----------------------------- Extraction -----------------------------


@dataclass
class ExtractedReportedVariant:
    tier: Optional[int]
    variant_text: str
    gene: Optional[str] = None
    exon_intron: Optional[str] = None
    vaf: Optional[str] = None
    simple_id: Optional[str] = None


class ReportVariantExtractor:
    def extract(self, html: str) -> List[ExtractedReportedVariant]:
        soup = BeautifulSoup(html, "html.parser")

        anchor = soup.find(
            "span", class_="report_header", string=lambda s: s and s.strip() == "Analysresultat"
        )
        if not anchor:
            return []

        tables = list(anchor.find_all_next("table", class_="variant_table"))
        if not tables:
            return []

        out: List[ExtractedReportedVariant] = []

        for table in tables:
            header_tr = table.find("tr")
            if not header_tr:
                continue

            headers = [th.get_text(" ", strip=True) for th in header_tr.find_all(["th", "td"])]
            header_map = {h.strip().lower(): i for i, h in enumerate(headers)}

            def col(*names: str) -> Optional[int]:
                for n in names:
                    n_l = n.lower()
                    for h, idx in header_map.items():
                        if h == n_l or n_l in h:
                            return idx
                return None

            idx_gene = col("Gen", "Gene")
            idx_mut = col("Mutation", "Variant", "HGVSc", "HGVSp")
            idx_exon = col("Exon/Intron", "Exon", "Intron")
            idx_vaf = col("Variantfrekvens", "VAF", "AF", "Frekvens")
            idx_class = col("Klassificering", "Class", "Tier")

            if idx_gene is None or idx_mut is None or idx_class is None:
                continue

            for tr in table.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if not tds:
                    continue

                cells = [td.get_text(" ", strip=True) for td in tds]

                def get(i: Optional[int]) -> str:
                    if i is None or i < 0 or i >= len(cells):
                        return ""
                    return cells[i].strip()

                gene = get(idx_gene) or None
                mut_raw = get(idx_mut)
                cls_raw = get(idx_class)
                exon = get(idx_exon) or None
                vaf = get(idx_vaf) or None

                tier = parse_tier(cls_raw)

                mut = normalize_variant_text(mut_raw)
                if mut.startswith("p."):
                    mut = normalize_hgvsp_three_letter(mut)

                if not mut or not gene:
                    continue

                out.append(
                    ExtractedReportedVariant(
                        tier=tier,
                        variant_text=mut,
                        gene=gene,
                        exon_intron=exon,
                        vaf=vaf,
                    )
                )

        # Deduplicate (gene, tier, variant_text)
        uniq = {}
        for x in out:
            uniq[(x.gene, x.tier, x.variant_text)] = x
        return list(uniq.values())


# ----------------------------- DB Resolver -----------------------------


@dataclass
class DBConfig:
    samples_coll: str
    variants_coll: str
    annotations_coll: str
    reported_coll: str

    ann_variant_field: str = "variant"
    ann_gene_field: str = "gene"
    ann_class_field: str = "class"
    ann_assay_field: str = "assay"
    ann_subpanel_field: str = "subpanel"
    ann_time_field: str = "time_created"
    ann_text_field: str = "text"

    sample_comments_field: str = "comments"
    sample_comment_time_field: str = "time_created"


class ReportedVariantsBackfiller:
    def __init__(self, db, cfg: DBConfig, extractor: ReportVariantExtractor, logger):
        self.db = db
        self.cfg = cfg
        self.extractor = extractor
        self.logger = logger

        self.samples = db[cfg.samples_coll]
        self.variants = db[cfg.variants_coll]
        self.annotations = db[cfg.annotations_coll]
        self.reported = db[cfg.reported_coll]

    def _log(self, msg: str, level: str = "info") -> None:
        getattr(self.logger, level.lower(), self.logger.info)(msg)

    def report_already_materialized(self, report_oid: ObjectId, report_id: str) -> bool:
        q = {"$or": [{"report_oid": report_oid}, {"report_id": report_id}]}
        return self.reported.find_one(q, {"_id": 1}) is not None

    def find_sample_comment_oid(
        self, sample_doc: Dict[str, Any], report_dt: dt.datetime
    ) -> Optional[ObjectId]:
        """
        Return latest visible sample comment (_id) whose time_created <= report_dt.
        Hidden comments (hidden=True) are skipped.
        """
        comments = sample_doc.get(self.cfg.sample_comments_field) or []
        best = None
        best_dt = None

        for c in comments:
            if not isinstance(c, dict):
                continue

            # Skip hidden comments
            if c.get("hidden") is True:
                continue

            cdt = parse_iso_dt(c.get(self.cfg.sample_comment_time_field))
            if cdt is None or cdt > report_dt:
                continue

            if best_dt is None or cdt > best_dt:
                best_dt = cdt
                best = c

        return best.get("_id") if best else None

    def find_variant_doc(
        self, sample_oid: ObjectId, extracted: ExtractedReportedVariant
    ) -> Optional[Dict[str, Any]]:
        sample_id_str = str(sample_oid)

        # single query: gene + (HGVSp OR HGVSc OR simple_id)
        q: Dict[str, Any] = {
            "SAMPLE_ID": sample_id_str,
            "INFO.selected_CSQ.SYMBOL": extracted.gene,
            "$or": [
                {"INFO.selected_CSQ.HGVSp": extracted.variant_text},
                {"INFO.selected_CSQ.HGVSc": extracted.variant_text},
            ],
        }
        if extracted.simple_id:
            q["$or"].append({"simple_id": extracted.simple_id})

        return self.variants.find_one(
            q,
            projection={
                "_id": 1,
                "simple_id": 1,
                "simple_id_hash": 1,
                "variant_class": 1,
                "INFO": 1,
            },
        )

    def find_latest_annotation_oid(
        self,
        *,
        variant_text: str,
        tier: Optional[int],
        gene: str,
        assay: Optional[str],
        subpanel: Optional[str],
        report_dt: dt.datetime,
    ) -> Optional[ObjectId]:
        """
        Tier/class annotation:
        - match on gene + variant + class/tier + assay (+ subpanel if present)
        - time_created <= report_dt
        """
        if not gene:
            return None

        q: Dict[str, Any] = {
            self.cfg.ann_gene_field: gene,
            self.cfg.ann_variant_field: variant_text,
            self.cfg.ann_time_field: {"$lte": report_dt},
        }
        if tier is not None:
            q[self.cfg.ann_class_field] = tier
        if assay:
            q[self.cfg.ann_assay_field] = assay
        if subpanel:
            q[self.cfg.ann_subpanel_field] = subpanel

        doc = self.annotations.find_one(
            q, sort=[(self.cfg.ann_time_field, -1)], projection={"_id": 1}
        )
        return doc["_id"] if doc else None

    def find_latest_annotation_text_oid(
        self,
        *,
        variant_text: str,
        gene: str,
        assay: Optional[str],
        subpanel: Optional[str],
        report_dt: dt.datetime,
    ) -> Optional[ObjectId]:
        """
        "Text annotation" (non-class):
        - match on gene + variant + assay (+ subpanel)
        - must have `text`
        - time_created <= report_dt
        """
        if not gene:
            return None

        q: Dict[str, Any] = {
            self.cfg.ann_gene_field: gene,
            self.cfg.ann_variant_field: variant_text,
            self.cfg.ann_time_field: {"$lte": report_dt},
            self.cfg.ann_text_field: {"$exists": True, "$ne": ""},
        }
        if assay:
            q[self.cfg.ann_assay_field] = assay
        if subpanel:
            q[self.cfg.ann_subpanel_field] = subpanel

        doc = self.annotations.find_one(
            q, sort=[(self.cfg.ann_time_field, -1)], projection={"_id": 1}
        )
        return doc["_id"] if doc else None

    def build_reported_variant_doc(
        self,
        *,
        sample_doc: Dict[str, Any],
        report_obj: Dict[str, Any],
        extracted: ExtractedReportedVariant,
        variant_doc: Dict[str, Any],
    ) -> Dict[str, Any]:
        report_oid: ObjectId = report_obj["_id"]
        sample_oid: ObjectId = sample_doc["_id"]

        report_dt = parse_iso_dt(report_obj.get("time_created")) or dt.datetime.utcnow()

        raw_assay = sample_doc.get("assay")
        assay = map_sample_assay_to_annotation_assay(raw_assay)
        subpanel = None

        variant_text = normalize_variant_text(extracted.variant_text)
        tier = extracted.tier

        gene = safe_get(variant_doc, "INFO.selected_CSQ.SYMBOL")
        transcript = safe_get(variant_doc, "INFO.selected_CSQ.Feature")
        hgvsp = safe_get(variant_doc, "INFO.selected_CSQ.HGVSp")
        hgvsc = safe_get(variant_doc, "INFO.selected_CSQ.HGVSc")

        ann_oid = self.find_latest_annotation_oid(
            variant_text=variant_text,
            tier=tier,
            gene=gene,
            assay=assay,
            subpanel=subpanel,
            report_dt=report_dt,
        )
        ann_text_oid = self.find_latest_annotation_text_oid(
            variant_text=variant_text,
            gene=gene,
            assay=assay,
            subpanel=subpanel,
            report_dt=report_dt,
        )

        sample_comment_oid = self.find_sample_comment_oid(sample_doc, report_dt)

        return {
            "report_oid": report_oid,
            "sample_oid": sample_oid,
            "simple_id": variant_doc.get("simple_id"),
            "sample_name": sample_doc.get("name") or sample_doc.get("id"),
            "report_id": report_obj.get("report_id"),
            "created_by": report_obj.get("author"),
            "var_oid": variant_doc.get("_id"),
            "annotation_oid": ann_oid,
            "annotation_text_oid": ann_text_oid,
            "sample_comment_oid": sample_comment_oid,
            "var_type": variant_doc.get("variant_class"),
            "simple_id_hash": variant_doc.get("simple_id_hash"),
            "tier": tier,
            "gene": gene,
            "transcript": transcript,
            "hgvsp": hgvsp,
            "hgvsc": hgvsc,
            "variant": variant_text,
            "created_on": report_dt,
        }

    def run_to_jsonl(
        self,
        *,
        sample_query: Dict[str, Any],
        out_prefix: str,
        dry_run: bool,
        limit_samples: Optional[int],
        limit_reports: Optional[int],
    ) -> Tuple[int, int, int, str, str]:
        """
        Writes JSONL files.
        Returns: (samples_scanned, reports_scanned, docs_success, success_path, error_path)
        """
        samples_scanned = 0
        reports_scanned = 0
        docs_success = 0

        success_docs: List[Dict[str, Any]] = []
        error_docs: List[Dict[str, Any]] = []

        cursor = self.samples.find(
            sample_query,
            projection={"reports": 1, "name": 1, "id": 1, "assay": 1, "comments": 1},
        )
        if limit_samples:
            cursor = cursor.limit(limit_samples)

        for sample in cursor:
            samples_scanned += 1
            sample_name = sample.get("name") or sample.get("id") or str(sample["_id"])

            reports = sample.get("reports") or []
            if not reports:
                continue

            iter_reports = reports[:limit_reports] if limit_reports else reports

            for r in iter_reports:
                if not isinstance(r, dict):
                    continue
                if r.get("report_type") != "html":
                    continue

                report_oid = r.get("_id")
                report_id = r.get("report_id")
                filepath = r.get("filepath")

                if not report_oid or not report_id or not filepath:
                    error_docs.append(
                        {
                            "kind": "report_error",
                            "sample_name": sample_name,
                            "sample_oid": sample["_id"],
                            "report_oid": report_oid,
                            "report_id": report_id,
                            "filepath": filepath,
                            "error": "missing_report_fields",
                            "report_obj": r,
                        }
                    )
                    continue

                reports_scanned += 1

                if self.report_already_materialized(report_oid, report_id):
                    self._log(
                        f"[SKIP] Already materialized report_id={report_id} sample={sample_name}"
                    )
                    continue

                if not os.path.exists(filepath):
                    error_docs.append(
                        {
                            "kind": "report_error",
                            "sample_name": sample_name,
                            "sample_oid": sample["_id"],
                            "report_oid": report_oid,
                            "report_id": report_id,
                            "filepath": filepath,
                            "error": "report_file_missing",
                        }
                    )
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        html = f.read()
                except Exception as e:
                    error_docs.append(
                        {
                            "kind": "report_error",
                            "sample_name": sample_name,
                            "sample_oid": sample["_id"],
                            "report_oid": report_oid,
                            "report_id": report_id,
                            "filepath": filepath,
                            "error": f"report_read_failed: {e}",
                        }
                    )
                    continue

                extracted = self.extractor.extract(html)
                if not extracted:
                    error_docs.append(
                        {
                            "kind": "report_error",
                            "sample_name": sample_name,
                            "sample_oid": sample["_id"],
                            "report_oid": report_oid,
                            "report_id": report_id,
                            "filepath": filepath,
                            "error": "no_variants_extracted",
                        }
                    )
                    continue

                for ex in extracted:
                    vdoc = self.find_variant_doc(sample["_id"], ex)
                    if not vdoc:
                        # keep same structure but mark error
                        error_docs.append(
                            {
                                "kind": "unmatched_variant",
                                "sample_name": sample_name,
                                "sample_oid": sample["_id"],
                                "report_oid": report_oid,
                                "report_id": report_id,
                                "filepath": filepath,
                                "extracted": {
                                    "gene": ex.gene,
                                    "variant_text": ex.variant_text,
                                    "tier": ex.tier,
                                    "exon_intron": ex.exon_intron,
                                    "vaf": ex.vaf,
                                    "simple_id": ex.simple_id,
                                },
                                "error": "variant_not_found_in_variants_collection",
                            }
                        )
                        continue

                    doc = self.build_reported_variant_doc(
                        sample_doc=sample,
                        report_obj=r,
                        extracted=ex,
                        variant_doc=vdoc,
                    )
                    success_docs.append(doc)
                    docs_success += 1

        success_path = f"{out_prefix}.success.jsonl"
        error_path = f"{out_prefix}.errors.jsonl"

        write_jsonl(success_path, success_docs)
        write_jsonl(error_path, error_docs)

        if dry_run:
            self._log(
                f"[DRY] Wrote JSONL only: {success_path} ({docs_success}) and {error_path} ({len(error_docs)})"
            )

        return samples_scanned, reports_scanned, docs_success, success_path, error_path

    def insert_from_jsonl(
        self, jsonl_path: str, ordered: bool = False, batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Insert docs from a JSONL file that uses {"$oid": "..."} and {"$date": "..."} wrappers.

        Requires UNIQUE index:
        { report_oid: 1, var_oid: 1 } unique

        Behavior:
        - inserts everything with insert_many(ordered=False)
        - skips duplicates automatically (BulkWriteError code 11000)
        - continues inserting the rest

        Returns counters:
        { "inserted": X, "duplicates": Y, "other_errors": Z }
        """
        counts = {"inserted": 0, "duplicates": 0, "other_errors": 0}

        def flush(batch_docs: List[Dict[str, Any]]) -> None:
            if not batch_docs:
                return

            try:
                res = self.reported.insert_many(batch_docs, ordered=ordered)
                counts["inserted"] += len(res.inserted_ids)
            except BulkWriteError as bwe:
                # When ordered=False, Mongo still inserts non-duplicates, then reports errors for duplicates.
                details = bwe.details or {}
                write_errors = details.get("writeErrors", []) or []

                dup = 0
                other = 0
                for e in write_errors:
                    # 11000 = duplicate key
                    if e.get("code") == 11000:
                        dup += 1
                    else:
                        other += 1

                counts["duplicates"] += dup
                counts["other_errors"] += other

                # inserted count is not always included reliably, but usually is:
                n_inserted = details.get("nInserted")
                if isinstance(n_inserted, int):
                    counts["inserted"] += n_inserted
                else:
                    # fallback: assume all except errors went in
                    counts["inserted"] += max(0, len(batch_docs) - len(write_errors))

        with open(jsonl_path, "r", encoding="utf-8") as f:
            batch: List[Dict[str, Any]] = []
            for line in f:
                line = line.strip()
                if not line:
                    continue

                raw = json.loads(line)
                doc = extjson_to_native(raw)
                batch.append(doc)

                if len(batch) >= batch_size:
                    flush(batch)
                    batch = []

            if batch:
                flush(batch)

        return counts


# ----------------------------- CLI -----------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Backfill reported_variants by scanning sample HTML reports, output JSONL, optionally insert into MongoDB."
    )

    p.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB URI, e.g. mongodb://localhost:27017",
    )
    p.add_argument("--db", required=True, help="Database name, e.g. coyote3")

    p.add_argument("--samples", default="samples", help="Samples collection name")
    p.add_argument("--variants", default="variants", help="Variants collection name")
    p.add_argument("--annotations", default="annotation", help="Annotations collection name")
    p.add_argument(
        "--reported", default="reported_variants", help="Reported variants collection name"
    )

    p.add_argument("--verbose", action="store_true", help="Verbose logging")

    # Subset / filters
    p.add_argument(
        "--sample-names",
        default=None,
        help='Comma-separated sample names to process, e.g. "25AB00000p-2,25AB00000p-1". If omitted: all samples.',
    )
    p.add_argument(
        "--assay", default=None, help="Only process samples with this assay (exact match)"
    )
    p.add_argument(
        "--sample-name-regex", default=None, help="Only process samples where name matches regex"
    )

    p.add_argument(
        "--limit-samples", type=int, default=None, help="Limit number of samples processed"
    )
    p.add_argument(
        "--limit-reports", type=int, default=None, help="Limit number of reports per sample"
    )

    # Output
    p.add_argument(
        "--out-prefix", default="reported_variants", help="Output prefix for JSONL files"
    )

    # Modes
    p.add_argument("--dry-run", action="store_true", help="Do not insert; only write JSONL outputs")
    p.add_argument(
        "--insert", action="store_true", help="Insert success JSONL into Mongo after generation"
    )
    p.add_argument(
        "--from-json",
        default=None,
        help="Instead of scanning reports, insert docs from an existing JSONL file (success file).",
    )

    # Annotation mapping
    p.add_argument("--ann-variant-field", default="variant")
    p.add_argument("--ann-class-field", default="class")
    p.add_argument("--ann-assay-field", default="assay")
    p.add_argument("--ann-subpanel-field", default="subpanel")
    p.add_argument("--ann-time-field", default="time_created")
    p.add_argument("--ann-text-field", default="text")
    p.add_argument("--ann-gene-field", default="gene")

    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    logger = setup_logger(f"{args.out_prefix}.log", args.verbose)

    logger.info("=== Starting reported_variants backfill ===")

    # Sys Info
    logger.info(f"Host: {socket.gethostname()}")
    logger.info(f"User: {getpass.getuser()}")
    logger.info(f"PID: {os.getpid()}")

    # Core DB / mode
    logger.info(f"Mongo URI: {args.mongo_uri}")
    logger.info(f"Database: {args.db}")
    logger.info(
        f"Collections: samples={args.samples}, variants={args.variants}, "
        f"annotations={args.annotations}, reported={args.reported}"
    )

    # Execution mode
    logger.info(f"Mode: {'FROM_JSON' if args.from_json else 'SCAN_REPORTS'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Insert after JSONL: {args.insert}")

    # Sample selection
    logger.info(f"Sample names filter: {args.sample_names or 'ALL'}")
    logger.info(f"Sample name regex: {args.sample_name_regex or 'NONE'}")
    logger.info(f"Assay filter: {args.assay or 'ALL'}")

    # Limits (important for partial backfills)
    logger.info(f"Limit samples: {args.limit_samples or 'NONE'}")
    logger.info(f"Limit reports per sample: {args.limit_reports or 'NONE'}")

    # Output
    logger.info(f"Output prefix: {args.out_prefix}")
    logger.info(f"Success JSONL: {args.out_prefix}.success.jsonl")
    logger.info(f"Error JSONL: {args.out_prefix}.errors.jsonl")
    logger.info(f"Log file: {args.out_prefix}.log")

    # Annotation matching configuration (VERY important for debugging)
    logger.info(
        "Annotation mapping: "
        f"variant={args.ann_variant_field}, "
        f"gene={args.ann_gene_field}, "
        f"class={args.ann_class_field}, "
        f"assay={args.ann_assay_field}, "
        f"subpanel={args.ann_subpanel_field}, "
        f"time={args.ann_time_field}, "
        f"text={args.ann_text_field}"
    )

    logger.info("===================================================")

    cfg = DBConfig(
        samples_coll=args.samples,
        variants_coll=args.variants,
        annotations_coll=args.annotations,
        reported_coll=args.reported,
        ann_variant_field=args.ann_variant_field,
        ann_class_field=args.ann_class_field,
        ann_assay_field=args.ann_assay_field,
        ann_subpanel_field=args.ann_subpanel_field,
        ann_time_field=args.ann_time_field,
        ann_text_field=args.ann_text_field,
        ann_gene_field=args.ann_gene_field,
    )

    client = MongoClient(args.mongo_uri)
    db = client[args.db]

    extractor = ReportVariantExtractor()
    backfiller = ReportedVariantsBackfiller(db, cfg, extractor, logger=logger)

    # Mode: insert from existing JSONL
    if args.from_json:
        inserted = backfiller.insert_from_jsonl(args.from_json, ordered=False)
        print(f"Inserted {inserted} docs from {args.from_json} into {args.reported}")
        return 0

    # Build sample_query
    sample_query: Dict[str, Any] = {}

    # specific list
    if args.sample_names:
        names = [x.strip() for x in args.sample_names.split(",") if x.strip()]
        # match either "name" or "id" (you use both patterns)
        sample_query["$or"] = [{"name": {"$in": names}}, {"id": {"$in": names}}]

    if args.assay:
        sample_query["assay"] = args.assay

    if args.sample_name_regex:
        # apply to name field; if you want to include id too, add OR
        sample_query["name"] = {"$regex": args.sample_name_regex}

    samples_scanned, reports_scanned, docs_success, success_path, error_path = (
        backfiller.run_to_jsonl(
            sample_query=sample_query,
            out_prefix=args.out_prefix,
            dry_run=args.dry_run,
            limit_samples=args.limit_samples,
            limit_reports=args.limit_reports,
        )
    )

    print(
        f"JSONL written.\n"
        f"  samples_scanned={samples_scanned}\n"
        f"  reports_scanned={reports_scanned}\n"
        f"  success_docs={docs_success}\n"
        f"  success_file={success_path}\n"
        f"  error_file={error_path}"
    )

    if args.insert and not args.dry_run:
        inserted = backfiller.insert_from_jsonl(success_path, ordered=False)
        print(f"Inserted {inserted} docs into {args.reported} from {success_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
