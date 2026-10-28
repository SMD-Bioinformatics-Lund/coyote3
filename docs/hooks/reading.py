"""Attach explicit task navigation without changing documentation page URLs."""

from pathlib import Path

import yaml


def on_config(config):
    """Load ordered reading paths from the documentation's reviewed source.

    Args:
        config: MkDocs configuration whose documentation directory owns the paths file.

    Returns:
        Configuration with reading-path metadata for page-context assembly.
    """
    source = Path(config.docs_dir) / "reading-paths.yml"
    config.extra["reading_paths"] = yaml.safe_load(source.read_text(encoding="utf-8"))["paths"]
    return config


def on_page_context(context, page, config, nav):
    """Resolve task links to built pages and keep unrelated references outside the path.

    Args:
        context: Template context for the current page.
        page: Current Markdown page with a stable source URI.
        config: MkDocs configuration containing the reading paths.
        nav: Built navigation used to resolve URLs without hardcoded deployment prefixes.

    Returns:
        Context with the matching task, its position, and explicit next/previous links.

    Raises:
        ValueError: A reading-path page is absent from the documentation navigation.
    """
    pages = {item.file.src_uri: item for item in nav.pages}
    for path in config.extra["reading_paths"]:
        entries = []
        for entry in path["pages"]:
            source = entry["file"]
            if source not in pages:
                raise ValueError(f"Reading path references an unlisted page: {source}")
            url = pages[source].url
            if entry.get("anchor"):
                url += "#" + entry["anchor"]
            entries.append({**entry, "url": url})
        for index, entry in enumerate(entries):
            if entry["file"] == page.file.src_uri:
                context["reading_path"] = {
                    "title": path["title"],
                    "entries": entries,
                    "position": index + 1,
                    "previous": entries[index - 1] if index else None,
                    "next": entries[index + 1] if index + 1 < len(entries) else None,
                }
                return context
    return context
