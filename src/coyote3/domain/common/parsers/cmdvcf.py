"""VCF parsing helpers used by ingestion flows."""

from __future__ import annotations

from typing import Any

from pysam import VariantFile


def parse_vcf(infile: str) -> tuple[Any, list[dict[str, Any]]]:
    """Read all records and close the VCF even if parsing fails.

    Args:
        infile: Local VCF or BCF filename accepted by pysam.

    Returns:
        Source header and normalized record dictionaries.

    Raises:
        OSError: The source cannot be opened or read.
        ValueError: Pysam rejects the file or a record cannot be decoded.
    """
    bcf_in = VariantFile(infile)
    header = bcf_in.header
    vcf_records: list[dict[str, Any]] = []
    try:
        for record in bcf_in.fetch():
            vcf_records.append(parse_variant(record, header))
    finally:
        bcf_in.close()
    return header, vcf_records


def fix_gt(gt_dict: dict[str, Any], samples: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize sample fields while preserving phase and missing genotype alleles.

    Args:
        gt_dict: Pysam sample mappings, or plain mappings for unphased evidence.
        samples: Sample names in the required output order.

    Returns:
        Sample dictionaries with source IDs and the FORMAT field names.
    """
    gt_list: list[dict[str, Any]] = []
    format_list: list[str] = []
    for sample in samples:
        format_list = list(dict(gt_dict[sample]).keys())
        sample_dict = dict(gt_dict[sample])
        for key in sample_dict:
            if key == "GT":
                separator = "|" if getattr(gt_dict[sample], "phased", False) else "/"
                sample_dict["GT"] = separator.join(
                    "." if allele is None else str(allele) for allele in sample_dict["GT"]
                )
            else:
                sample_dict[key] = unravel_tuples(sample_dict[key])
        sample_dict["_sample_id"] = sample
        gt_list.append(sample_dict)
    return gt_list, format_list


def parse_variant(record: Any, header: Any) -> dict[str, Any]:
    """Convert a pysam record to coyote-style dict shape."""
    var_id = record.id if record.id is not None else "."
    gt_list, format_list = fix_gt(dict(record.samples), list(header.samples))
    return {
        "CHROM": record.chrom,
        "POS": record.pos,
        "ID": var_id,
        "REF": record.ref,
        "ALT": ",".join(list(record.alts)),
        "QUAL": record.qual,
        "FILTER": ";".join(list(record.filter)),
        "INFO": fix_info(dict(record.info), header),
        "FORMAT": format_list,
        "GT": gt_list,
    }


def fix_info(info_dict: dict[str, Any], header: Any) -> dict[str, Any]:
    """Decode scalar or list CSQ/ANN annotations and normalize other INFO fields.

    Args:
        info_dict: Decoded VCF INFO values.
        header: VCF header containing each annotation's field description.

    Returns:
        INFO dictionary with structured annotation lists.
    """
    new_info_dict: dict[str, Any] = {}
    for key, value in info_dict.items():
        if key == "CSQ":
            new_info_dict["CSQ"] = csq([value] if isinstance(value, str) else list(value), header)
        elif key == "ANN":
            new_info_dict["ANN"] = snpeff(
                [value] if isinstance(value, str) else list(value), header
            )
        else:
            new_info_dict[key] = unravel_tuples(value)
    return new_info_dict


def csq(transcripts: list[str], header: Any) -> list[dict[str, Any]]:
    """Decode VEP annotations using the field order at the end of the description.

    Args:
        transcripts: Pipe-delimited transcript annotations.
        header: VCF header defining INFO/CSQ; trailing whitespace is ignored.

    Returns:
        Transcript dictionaries with consequence terms split on ampersands.
    """
    csq_meta = header.info["CSQ"]
    csq_keys = str(csq_meta.description).strip().split(" ").pop().split("|")
    csq_list: list[dict[str, Any]] = []
    for transcript in transcripts:
        csq_dict: dict[str, Any] = {}
        transcript_anno = transcript.split("|")
        for key, anno in zip(csq_keys, transcript_anno):
            if key == "Consequence":
                csq_dict[key] = anno.split("&")
            else:
                csq_dict[key] = anno
        csq_list.append(csq_dict)
    return csq_list


def snpeff(transcripts: list[str], header: Any) -> list[dict[str, Any]]:
    """Decode SnpEff annotations without retaining header-description quote marks.

    Args:
        transcripts: Pipe-delimited transcript annotations.
        header: VCF header defining INFO/ANN's field order.

    Returns:
        Annotation dictionaries with consequence terms split on ampersands.
    """
    snpeff_meta = header.info["ANN"]
    snpeff_keys = [key.strip().strip("'") for key in snpeff_meta.description.split(" | ")]
    snpeff_keys[0] = "Allele"
    snpeff_list: list[dict[str, Any]] = []
    for transcript in transcripts:
        snpeff_dict: dict[str, Any] = {}
        transcript_anno = transcript.split("|")
        for key, anno in zip(snpeff_keys, transcript_anno):
            if key == "Annotation":
                snpeff_dict[key] = anno.split("&")
            else:
                snpeff_dict[key] = anno
        snpeff_list.append(snpeff_dict)
    return snpeff_list


def unravel_tuples(value: Any) -> Any:
    """Convert tuple-ish pysam values to comma-separated strings."""
    if isinstance(value, tuple):
        try:
            value = ",".join(list(value))
        except Exception:
            value = ",".join(str(x) for x in list(value))
    return value
