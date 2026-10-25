"""Filesystem implementation of registered plot and saved-report artifact access."""

import mimetypes
from pathlib import Path

from api.infra.artifact_paths import resolve_sample_file_path
from coyote3.application.operations.models import FileArtifact
from coyote3.domain.common.errors import api_error


class FilesystemRegisteredArtifacts:
    """Resolve only references selected by an authorized application operation."""

    def plot(self, reference: str, filename: str) -> FileArtifact:
        """Validate mounted-data confinement, basename and the existing raster media allowlist."""
        path = resolve_sample_file_path(reference)
        if path.name != filename:
            raise api_error(404, "Registered CNV profile image file is not available")
        media_type = mimetypes.guess_type(path.name)[0]
        if media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/tiff"}:
            raise api_error(415, "The registered CNV profile must be a raster image")
        return FileArtifact(path=str(path.resolve()), filename=path.name, media_type=media_type)

    def report(
        self, reference: str | None, filename: str | None, *, media_type: str, inline: bool
    ) -> FileArtifact:
        """Resolve the registered report file before preparing an HTTP or local SDK artifact."""
        if not reference:
            raise api_error(404, "Report file path is not available")
        path = Path(reference)
        if not path.exists() or not path.is_file():
            raise api_error(404, "Report file not found")
        return FileArtifact(
            path=str(path),
            filename=filename or path.name,
            media_type=media_type,
            text=path.read_text(encoding="utf-8", errors="replace") if inline else None,
        )
