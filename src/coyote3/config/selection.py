"""Select a center profile explicitly before constructing process-wide contracts."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

CENTER_CONFIGURATION_FORMAT = 1


class CenterConfiguration(BaseModel):
    """External policy files selected by a host; no environment discovery occurs."""

    model_config = ConfigDict(frozen=True)
    directory: Path | None = None
    authentication_providers: str | None = None

    def require_files(self) -> None:
        """Reject incomplete profiles before the host initializes application services.

        Raises:
            FileNotFoundError: A required clinical vocabulary or filter metadata file is missing.
            ValueError: A staged manifest declares an unsupported configuration format.
        """
        if self.directory is None:
            return
        for name in ("clinical_vocabulary.toml", "filter_flag_metadata.yaml"):
            path = self.directory / name
            if not path.is_file():
                raise FileNotFoundError(f"Required center configuration file is missing: {path}")
        manifest = self.directory / "manifest.json"
        if manifest.is_file():
            version = json.loads(manifest.read_text(encoding="utf-8")).get("format")
            if type(version) is not int or version != CENTER_CONFIGURATION_FORMAT:
                raise ValueError(f"Unsupported center configuration format: {version!r}")


_selected: CenterConfiguration | None = None
_frozen = False


def configure_center(configuration: CenterConfiguration) -> None:
    """Bind a validated file set before importing vocabulary-dependent contracts.

    Args:
        configuration: External center directory supplied explicitly by the host.

    Raises:
        FileNotFoundError: Required files are absent.
        RuntimeError: Contracts already use another profile; restart the process to change it.

    Notes:
        One process serves one center. Configuration changes require a restart;
        changing global Pydantic contract definitions during requests is unsupported.
        Content is validated by the vocabulary and flag loaders at startup.
    """
    global _selected
    if configuration.directory is not None:
        configuration = configuration.model_copy(
            update={"directory": configuration.directory.expanduser().resolve()}
        )
    configuration.require_files()
    if _frozen and configuration != _selected:
        raise RuntimeError("Select center configuration before importing application contracts")
    _selected = configuration


def center_policy_path(name: str, default: Path) -> Path:
    """Resolve an immutable profile input or a software-owned default.

    Args:
        name: Policy filename inside the selected center directory.
        default: Bundled software default used for standalone library operations.

    Returns:
        Explicit center policy path, or the packaged default when no profile was selected.
    """
    global _frozen
    _frozen = True
    return _selected.directory / name if _selected is not None and _selected.directory else default


def authentication_provider_override() -> str:
    """Return the host-supplied authentication selection without reading the environment."""
    return (_selected.authentication_providers or "") if _selected is not None else ""
