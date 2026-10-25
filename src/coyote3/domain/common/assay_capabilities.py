"""Resolve assay capabilities from the implemented family and input contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def supported_assay_analyses(
    *,
    family_analyses: Sequence[str],
    file_bindings: Mapping[str, Sequence[str]],
    expected_files: Sequence[str],
    declared_analyses: Sequence[str] | None,
) -> list[str]:
    """Return supported analyses in registry order, rejecting invalid declarations.

    Args:
        family_analyses: Implemented analyses permitted by the technical family.
        file_bindings: Required input alternatives for each implemented analysis.
        expected_files: Input types accepted by this assay.
        declared_analyses: Explicit subset, or None to use every eligible analysis.
            An empty list deliberately enables no analyses.

    Returns:
        The supported subset in the order defined by the capability registry.

    Raises:
        ValueError: A declared analysis lacks family support or an accepted input.
    """
    files = set(expected_files)
    eligible = [
        analysis
        for analysis in family_analyses
        if files.intersection(file_bindings.get(analysis, ()))
    ]
    if declared_analyses is None:
        return eligible
    declared = set(declared_analyses)
    invalid = sorted(declared - set(eligible))
    if invalid:
        raise ValueError(
            "Assay analyses require supported family and input files: " + ", ".join(invalid)
        )
    return [analysis for analysis in eligible if analysis in declared]
