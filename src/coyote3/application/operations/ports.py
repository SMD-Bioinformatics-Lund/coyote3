"""Artifact capabilities supplied by host composition to application operations."""

from typing import Protocol

from coyote3.application.operations.models import FileArtifact


class RegisteredArtifacts(Protocol):
    """Validate registered references and resolve deployment artifact content."""

    def plot(self, reference: str, filename: str) -> FileArtifact:
        """Resolve an existing registered raster artifact with an exact requested basename."""
        ...

    def report(
        self, reference: str | None, filename: str | None, *, media_type: str, inline: bool
    ) -> FileArtifact:
        """Resolve an existing saved artifact and optionally read inline HTML content."""
        ...
