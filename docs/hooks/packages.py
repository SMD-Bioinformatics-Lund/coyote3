# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Publish package-owned documentation without copying it into application guides."""

import posixpath
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = {
    "core": "core",
    "api": "api",
    "mongo": "adapters/mongo",
    "client": "clients/python",
    "relay": "services/relay",
    "atlas": "services/atlas",
    "demo": "services/demo",
    "frontend": "frontend",
}
_published: dict[Path, str] = {}
_INLINE_LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)(\))")
_REFERENCE_LINK = re.compile(r"(?m)^(\[[^\]\n]+\]:\s*)(\S+)")
_HTML_ASSET = re.compile(r"""(<(?:img|source)\b[^>]*\bsrc=["'])([^"']+)(["'])""", re.I)


def on_files(files, config):
    """Expose reviewed package guides and public metadata under package-specific URLs.

    Args:
        files: Application documentation files already discovered by MkDocs.
        config: Site configuration supplying the output directory and URL policy.

    Returns:
        Files including package guides backed by their authoritative source files.
    """
    _published.clear()
    for file in files:
        if file.abs_src_path:
            _published[Path(file.abs_src_path).resolve()] = file.src_uri
    for filename in ("LICENSE.txt", "COPYRIGHT.txt", "NOTICE.txt"):
        source = ROOT / filename
        if source.is_file():
            logical = f"project/{filename}"
            files.append(File.generated(config, logical, abs_src_path=str(source)))
            _published[source.resolve()] = logical
    server_metadata = ROOT / "pyproject.toml"
    if server_metadata.is_file():
        logical = "packages/server/pyproject.toml"
        files.append(File.generated(config, logical, abs_src_path=str(server_metadata)))
        _published[server_metadata.resolve()] = logical
    for name, directory in PROJECTS.items():
        project = ROOT / directory
        for source in sorted((project / "docs").rglob("*")):
            if not source.is_file() or source.suffix not in {
                ".md",
                ".svg",
                ".png",
                ".ico",
                ".webp",
            }:
                continue
            logical = f"packages/{name}/{source.relative_to(project / 'docs').as_posix()}"
            files.append(File.generated(config, logical, abs_src_path=str(source)))
            _published[source.resolve()] = logical
        if name == "api":
            source = project / "src/coyote_api/config/assets/coyote-api-logo.svg"
            if source.is_file():
                logical = f"packages/{name}/assets/coyote-api-logo.svg"
                files.append(File.generated(config, logical, abs_src_path=str(source)))
                _published[source.resolve()] = logical
        if name in {"relay", "atlas", "demo"}:
            source = project / f"src/coyote_{name}/assets/coyote-{name}-logo.svg"
            if source.is_file():
                logical = f"packages/{name}/assets/coyote-{name}-logo.svg"
                files.append(File.generated(config, logical, abs_src_path=str(source)))
                _published[source.resolve()] = logical
        if name == "atlas":
            for filename in ("NOTICE.txt", "LICENSE.txt"):
                source = project / "src/coyote_atlas/data/reference" / filename
                if source.is_file():
                    logical = f"packages/atlas/reference-data/{filename}"
                    files.append(File.generated(config, logical, abs_src_path=str(source)))
                    _published[source.resolve()] = logical
        for filename, public_name in (
            ("README.md", "overview.md"),
            ("CHANGELOG.md", "changelog.md"),
            ("CONTRIBUTING.md", "contributing.md"),
            ("LICENSE.txt", "LICENSE.txt"),
            ("COPYRIGHT.txt", "COPYRIGHT.txt"),
            ("NOTICE.txt", "NOTICE.txt"),
            ("pyproject.toml", "pyproject.toml"),
            ("package.json", "package.json"),
        ):
            source = project / filename
            if source.is_file():
                logical = f"packages/{name}/{public_name}"
                files.append(File.generated(config, logical, abs_src_path=str(source)))
                _published[source.resolve()] = logical
    return files


def on_page_markdown(markdown, page, **kwargs):
    """Translate repository-relative links to site URLs while preserving source links.

    Args:
        markdown: Original page text with links readable in the repository.
        page: Page identifying its actual source file and published URI.
        **kwargs: Additional MkDocs hook context, unused.

    Returns:
        Markdown whose known local links resolve within the published site.
        External URLs, fragments and unknown targets remain unchanged.
    """
    if not page.file.abs_src_path:
        return markdown
    directory = Path(page.file.abs_src_path).resolve().parent

    def rewrite(match, *, html: bool = False):
        """Resolve a source link against Markdown or the rendered HTML page URL.

        Args:
            match: Matched destination and its surrounding markup.
            html: Resolve raw HTML assets against the rendered URL when True.

        Returns:
            Rewritten markup, or the original when its destination is not published.
        """
        target = urlsplit(match[2])
        if target.scheme or target.netloc or not target.path or target.path.startswith("/"):
            return match[0]
        logical = _published.get((directory / target.path).resolve())
        if logical is None:
            return match[0]
        page_location = page.file.url if html else page.file.src_uri
        relative = posixpath.relpath(logical, posixpath.dirname(page_location) or ".")
        url = urlunsplit(("", "", relative, target.query, target.fragment))
        return match[1] + url + (match[3] if match.lastindex == 3 else "")

    return _HTML_ASSET.sub(
        lambda match: rewrite(match, html=True),
        _REFERENCE_LINK.sub(rewrite, _INLINE_LINK.sub(rewrite, markdown)),
    )
