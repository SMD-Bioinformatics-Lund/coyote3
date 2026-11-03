"""Prepare presentation values from previously evaluated clinical report inputs."""

from copy import deepcopy
from typing import Any

from coyote3.application.common.release_resources import assay_resource
from coyote3.application.reporting.clinical_rules.validation import REPORT_METADATA_SECTIONS


def report_scope_label(sample: dict, configuration: dict, diagnosis_repository: Any) -> str:
    """Resolve the report's diagnosis or panel display name and pairing context.

    Args:
        sample: Authorized sample supplying the diagnosis and paired-control flag.
        configuration: Resolved ASPC with its captured assay resource.
        diagnosis_repository: Repository resolving current registered diagnosis definitions.

    Returns:
        Display name with Swedish paired or unpaired analysis wording.

    Raises:
        ValueError: A non-base diagnosis has no registered display name.
    """
    diagnosis = str(sample.get("diagnosis_id") or "base").strip()
    if diagnosis.lower() in {"base", "na", "n/a"}:
        panel = assay_resource(configuration)
        name = panel.get("display_name") or panel.get("name") or panel.get("asp_id")
    else:
        record = diagnosis_repository.get_current(str(sample["asp_id"]), diagnosis)
        name = (record or {}).get("display_name")
        if not name:
            raise ValueError("Report diagnosis has no registered display name")
    pairing = "parad analys" if sample.get("paired") else "oparad analys"
    return f"{name} · {pairing}"


def prepare_render_context(
    context: dict[str, Any], *, analyte: str, preview: bool
) -> dict[str, Any]:
    """Add presentation defaults without evaluating clinical rules or selecting findings.

    Args:
        context: Prepared report data, including already evaluated clinical metadata.
        analyte: DNA or RNA workflow associated with these values.
        preview: Whether the existing preview notice and browser presentation apply.

    Returns:
        A new context preserving the caller's sample and configuration records.

    Raises:
        ValueError: Clinical rule evaluation supplied multiple values for a metadata field.
    """
    sample = dict(context.get("sample") or {})
    sample.setdefault("comments", [])
    sample.setdefault("report_num", 0)
    context = dict(context)
    sections = (context.get("clinical_rule_evaluation") or {}).get("sections", {})
    context["analysis_description"] = "\n\n".join(sections.get("analysis_description", []))
    for field in REPORT_METADATA_SECTIONS:
        values = sections.get(field, [])
        if len(values) > 1:
            raise ValueError(f"Clinical rules produced multiple values for {field}")
        context[field] = values[0] if values else ""
    context["assay_config"] = deepcopy(context.get("assay_config") or {})
    reporting = context["assay_config"].setdefault("reporting", {})
    reporting["report_header"] = (
        str(reporting.get("report_header") or "") + context["report_header_suffix"]
    )
    context["report_header"] = (
        str(context.get("report_header") or "") + context["report_header_suffix"]
    )
    context["sample"] = sample
    if analyte == "rna":
        context["fusions"] = [
            {
                **fusion,
                "report_selected_calls": [
                    call for call in fusion.get("calls", []) if call.get("selected") == 1
                ],
            }
            for fusion in context.get("fusions", [])
        ]
    context.setdefault("germline", False)
    context.setdefault("pdf", 0 if preview else 1)
    context["save"] = 0 if preview else 1
    return context
