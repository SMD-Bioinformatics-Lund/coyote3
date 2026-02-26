#!/usr/bin/env python3
"""Download third-party frontend assets into local static/vendor."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "coyote" / "static" / "vendor"

ASSETS = [
    (
        "https://unpkg.com/easymde/dist/easymde.min.css",
        STATIC_ROOT / "easymde" / "easymde.min.css",
    ),
    (
        "https://unpkg.com/easymde/dist/easymde.min.js",
        STATIC_ROOT / "easymde" / "easymde.min.js",
    ),
    (
        "https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js",
        STATIC_ROOT / "markdown-it" / "markdown-it.min.js",
    ),
]


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response:  # nosec B310
        content = response.read()
    destination.write_bytes(content)
    print(f"downloaded {url} -> {destination.relative_to(REPO_ROOT)}")


def main() -> None:
    for url, destination in ASSETS:
        _download(url, destination)


if __name__ == "__main__":
    main()
