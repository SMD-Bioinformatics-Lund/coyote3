"""Render GitHub-readable blockquote callouts using native Read the Docs classes."""

import re
from xml.etree.ElementTree import Element

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

CALLOUT = re.compile(r"^(Note|Info|Important|Tip|Warning|Caution|Danger)(?::.*)?$", re.I)
GITHUB_CALLOUT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\n|$)")


class NativeCallouts(Treeprocessor):
    """Convert only blockquotes with a standalone, recognized bold heading."""

    @staticmethod
    def _heading_kind(heading: Element) -> str | None:
        """Return the native callout class for a standalone recognized heading.

        Args:
            heading: Paragraph that may contain only a bold callout label.

        Returns:
            Native callout class, or None for ordinary paragraph content.
        """
        if heading.tag != "p" or len(heading) != 1 or (heading.text or "").strip():
            return None
        label = heading[0]
        if label.tag != "strong" or len(label) or (label.tail or "").strip():
            return None
        match = CALLOUT.fullmatch(label.text or "")
        if not match:
            return None
        kind = match[1].lower()
        return "note" if kind == "info" else kind

    def run(self, root: Element) -> Element:
        """Apply native markup while preserving body elements and ordinary quotes.

        Args:
            root: Parsed Markdown element tree before HTML serialization.

        Returns:
            The same tree with recognized callout containers and titles restyled.
        """
        # Normalize GitHub alert markers before applying the existing native renderer.
        for quote in list(root.iter("blockquote")):
            for position, child in reversed(list(enumerate(list(quote)))):
                if child.tag != "p":
                    continue
                match = GITHUB_CALLOUT.match(child.text or "")
                if match is None:
                    continue
                heading = Element("p")
                label = Element("strong")
                label.text = match[1].title()
                heading.append(label)
                child.text = (child.text or "")[match.end() :]
                quote.insert(position, heading)
                if not child.text and not len(child):
                    quote.remove(child)
        for parent in list(root.iter()):
            for quote in list(parent):
                if quote.tag != "blockquote" or not len(quote):
                    continue
                if self._heading_kind(quote[0]) is None:
                    continue
                # Markdown merges adjacent blockquotes; each callout heading starts a new box.
                sections: list[Element] = []
                for child in list(quote):
                    kind = self._heading_kind(child)
                    if kind:
                        sections.append(Element("div", {"class": f"admonition {kind}"}))
                        title = child[0].text
                        child.remove(child[0])
                        child.text = title
                        child.set("class", "admonition-title")
                    sections[-1].append(child)
                sections[-1].tail = quote.tail
                position = list(parent).index(quote)
                parent.remove(quote)
                for offset, section in enumerate(sections):
                    parent.insert(position + offset, section)
        return root


class NativeCalloutExtension(Extension):
    """Register callout conversion after inline Markdown has been parsed."""

    def extendMarkdown(self, md):  # noqa: N802
        """Attach the tree processor to the current Markdown renderer.

        Args:
            md: Markdown renderer configured by MkDocs.
        """
        md.treeprocessors.register(NativeCallouts(md), "native_callouts", 5)


def on_config(config):
    """Enable native callouts without changing Markdown sources used by GitHub.

    Args:
        config: MkDocs configuration for the current build.

    Returns:
        Configuration with the callout extension appended.
    """
    config["markdown_extensions"].append(NativeCalloutExtension())
    return config
