"""Check that documentation callouts preserve Markdown content and code examples."""

import runpy
from pathlib import Path

import markdown
import pytest

EXTENSION = runpy.run_path(str(Path(__file__).resolve().parents[2] / "docs/hooks/callouts.py"))[
    "NativeCalloutExtension"
]


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("Note", "note"),
        ("Info: Details", "note"),
        ("IMPORTANT", "important"),
        ("Warning", "warning"),
    ],
)
def test_recognized_callout_keeps_rich_content(title, kind):
    """Render the native title and preserve links, emphasis, and lists in the body."""
    rendered = markdown.markdown(
        f"> **{title}**\n>\n> See [guide](guide.md) and *details*.\n>\n> - First\n> - Second",
        extensions=[EXTENSION()],
    )
    assert f'class="admonition {kind}"' in rendered
    assert f'<p class="admonition-title">{title}</p>' in rendered
    assert '<a href="guide.md">guide</a>' in rendered
    assert "<em>details</em>" in rendered
    assert "<li>Second</li>" in rendered


@pytest.mark.parametrize(
    "source",
    ["> Ordinary quotation", "> **Other heading**\n>\n> Body", "> **Note** continues in prose"],
)
def test_ordinary_quotes_are_unchanged(source):
    """Do not reinterpret unknown headings or bold text embedded in a paragraph."""
    assert markdown.markdown(source, extensions=[EXTENSION()]) == markdown.markdown(source)


def test_fenced_code_is_not_converted_to_a_callout():
    """Keep a Markdown callout example literal inside a fenced code block."""
    source = "```markdown\n> **Warning**\n>\n> Example\n```"
    assert markdown.markdown(source, extensions=["fenced_code", EXTENSION()]) == markdown.markdown(
        source, extensions=["fenced_code"]
    )


def test_adjacent_callouts_keep_separate_titles_and_bodies():
    """Split consecutive Markdown quotations into independently styled callouts."""
    source = "> **Important**\n>\n> First body\n\n> **Note: Details**\n>\n> Second body"
    rendered = markdown.markdown(source, extensions=[EXTENSION()])
    assert rendered.count('class="admonition ') == 2
    first, second = rendered.split("</div>", maxsplit=1)
    assert "admonition important" in first
    assert "First body" in first
    assert "Second body" not in first
    assert "admonition note" in second
    assert "Second body" in second


@pytest.mark.parametrize("kind", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
@pytest.mark.parametrize("separator", ["\n>", ""])
def test_github_alerts_preserve_body_and_formatting(kind, separator):
    """GitHub alerts render native colored containers with intact rich body content."""
    source = f"> [!{kind}]{separator}\n> Read **this** [guide](guide.md).\n>\n> - Item"
    rendered = markdown.markdown(source, extensions=[EXTENSION()])
    assert f'class="admonition {kind.lower()}"' in rendered
    assert f'class="admonition-title">{kind.title()}</p>' in rendered
    assert "<strong>this</strong>" in rendered
    assert '<a href="guide.md">guide</a>' in rendered
    assert "<li>Item</li>" in rendered
    assert "[!" not in rendered


def test_github_alerts_in_code_remain_literal():
    """Alert syntax in a fenced example must not create a rendered alert."""
    source = "```markdown\n> [!WARNING]\n> Example\n```"
    assert markdown.markdown(source, extensions=["fenced_code", EXTENSION()]) == markdown.markdown(
        source, extensions=["fenced_code"]
    )
