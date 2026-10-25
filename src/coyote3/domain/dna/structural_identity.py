"""Identity and coordinate formatting for DNA structural findings."""

from typing import Any


def structural_position(finding: dict[str, Any]) -> str:
    """Return the source coordinate, including a recorded interval endpoint.

    Args:
        finding: Structural finding with CHROM, POS and optional inclusive END.

    Returns:
        CHROM:POS for a breakend, or CHROM:POS-END for an interval.
    """
    position = f"{finding.get('CHROM')}:{finding.get('POS')}"
    if finding.get("END") is not None:
        position += f"-{finding['END']}"
    return position


def translocation_annotation_identity(finding: dict[str, Any]) -> str:
    """Build the classification identity without conflating different interval ends.

    Args:
        finding: Structural finding with coordinates and ALT.

    Returns:
        Coordinate followed by ^ALT. Existing breakend identities are unchanged;
        newly supported symbolic intervals include their end coordinate.
    """
    return f"{structural_position(finding)}^{finding.get('ALT')}"
