"""Storage ports for bounded clinical finding selection.

Implementations translate Selection values and map results to the application's
clinical record vocabulary. Database cursors and executable query dictionaries
are implementation details of adapters.
"""

from typing import Any, Protocol

from coyote3.domain.selection import Selection


class SampleFindingReader(Protocol):
    """Read sample-owned finding candidates without accepting database syntax."""

    def preview_sample_findings(
        self, sample_id: str, query: Selection, limit: int = 10001
    ) -> list[dict[str, Any]]:
        """Return bounded candidates under an independently enforced sample scope.

        Args:
            sample_id: Authorized logical sample identity.
            query: Immutable clinical comparisons, never a storage query dictionary.
            limit: Maximum records, including an overflow sentinel; defaults to 10001.

        Returns:
            Clinical finding records in stable identity order.
        """
        ...
