# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Build patient and analysis metadata from resolved report context."""

from datetime import datetime

from .formatting import _value


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
