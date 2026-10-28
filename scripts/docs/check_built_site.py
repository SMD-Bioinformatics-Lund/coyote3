#!/usr/bin/env python3
"""Check rendered documentation links, section anchors and local page assets."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]


class BuiltPage(HTMLParser):
    """Collect link destinations and anchors from one rendered HTML page."""

    def __init__(self) -> None:
        """Initialize isolated destination and anchor collections."""
        super().__init__(convert_charrefs=True)
        self.targets: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record page links and local assets without executing scripts.

        Args:
            tag: HTML element name.
            attrs: Parsed attributes, with None for attributes without values.
        """
        attributes = dict(attrs)
        if identity := attributes.get("id"):
            self.anchors.add(identity)
        if tag == "a" and (name := attributes.get("name")):
            self.anchors.add(name)
        key = "href" if tag in {"a", "link"} else "src" if tag in {"img", "script"} else None
        if key and (target := attributes.get(key)):
            self.targets.append(target)


def check_site(directory: Path) -> tuple[int, list[str]]:
    """Validate local destinations inside a completed static documentation build.

    Args:
        directory: MkDocs output directory, built before invoking this function.

    Returns:
        Number of HTML pages inspected and deduplicated broken destinations.
        External links are not requested or verified.

    Raises:
        OSError: A rendered HTML file cannot be read.
    """
    root = directory.resolve()
    pages: dict[Path, BuiltPage] = {}
    for source in root.rglob("*.html"):
        page = BuiltPage()
        page.feed(source.read_text(encoding="utf-8"))
        pages[source] = page
    if not pages:
        return 0, [f"No built HTML pages in {root}; run mkdocs build first"]
    errors: set[str] = set()
    for source, page in pages.items():
        for target in page.targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            path = unquote(parsed.path)
            destination = (
                root / path.lstrip("/")
                if path.startswith("/")
                else source.parent / path
                if path
                else source
            ).resolve()
            if not destination.is_relative_to(root):
                errors.add(f"{source.relative_to(root)}: link escapes built site: {target}")
                continue
            if destination.is_dir():
                destination /= "index.html"
            if not destination.is_file():
                errors.add(f"{source.relative_to(root)}: missing destination: {target}")
            elif parsed.fragment and destination in pages:
                if unquote(parsed.fragment) not in pages[destination].anchors:
                    errors.add(f"{source.relative_to(root)}: missing section anchor: {target}")
    return len(pages), sorted(errors)


def main() -> int:
    """Report rendered-link failures using only local build output.

    Returns:
        Zero if every local link, anchor and HTML asset resolves; one otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    count, errors = check_site(args.site)
    for error in errors:
        print(error)
    if not errors:
        print(f"[ok] links, section anchors and assets checked across {count} built pages")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
