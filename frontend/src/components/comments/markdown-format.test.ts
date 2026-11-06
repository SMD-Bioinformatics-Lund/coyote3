import { describe, expect, it } from "vitest"

import { markdownToHtml } from "./markdown-format"

describe("markdownToHtml", () => {
  it("keeps formatting syntax literal inside code", () => {
    expect(markdownToHtml("`**literal**`")).toBe("<p><code>**literal**</code></p>")
    expect(markdownToHtml("```first\n\n**second**```" )).toContain("<pre><code>first\n\n**second**</code></pre>")
  })
  it("preserves text resembling internal escape markers", () => {
    expect(markdownToHtml("@@COYOTE_ESC_0@@")).toBe("<p>@@COYOTE_ESC_0@@</p>")
  })
  it("recognizes Windows newlines as paragraph boundaries", () => {
    expect(markdownToHtml("first\r\n\r\nsecond")).toBe("<p>first</p><p>second</p>")
  })
  it("removes accepted indentation before quote and list markers", () => {
    expect(markdownToHtml("  > quote")).toBe("<blockquote>quote</blockquote>")
    expect(markdownToHtml("  - item")).toBe("<ul><li>item</li></ul>")
  })
  it("preserves the starting number of ordered lists", () => {
    expect(markdownToHtml("3. third\n4. fourth")).toBe('<ol start="3"><li>third</li><li>fourth</li></ol>')
  })
  it("does not nest block headings inside paragraphs", () => {
    expect(markdownToHtml("# Heading")).toBe("<h1>Heading</h1>")
  })
  it("escapes raw HTML before applying supported formatting", () => {
    expect(markdownToHtml('<script>alert("x")</script> & text')).toBe(
      "<p>&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; text</p>",
    )
  })

  it("renders headings, emphasis, deletion, inline code, and fenced code", () => {
    const source = [
      "# Heading",
      "",
      "**bold** *italic* ~~removed~~ `inline`",
      "",
      "```const value = 1```",
    ].join("\n")

    const html = markdownToHtml(source)
    expect(html).toContain("<h1>Heading</h1>")
    expect(html).toContain("<strong>bold</strong>")
    expect(html).toContain("<em>italic</em>")
    expect(html).toContain("<del>removed</del>")
    expect(html).toContain("<code>inline</code>")
    expect(html).toContain("<pre><code>const value = 1</code></pre>")
  })

  it("renders links only for HTTP protocols", () => {
    const html = markdownToHtml(
      "[safe](https://example.test) [unsafe](javascript:alert(1))",
    )

    expect(html).toContain(
      '<a href="https://example.test" target="_blank" rel="noreferrer">safe</a>',
    )
    expect(html).toContain("[unsafe](javascript:alert(1))")
  })

  it("renders quote, unordered-list, ordered-list, table, and rule blocks", () => {
    const source = [
      "> first",
      "> second",
      "",
      "- alpha",
      "- beta",
      "",
      "1. one",
      "2. two",
      "",
      "Name | Value",
      "--- | ---",
      "A | 1",
      "B | 2",
      "",
      "---",
    ].join("\n")

    const html = markdownToHtml(source)
    expect(html).toContain("<blockquote>first<br>second</blockquote>")
    expect(html).toContain("<ul><li>alpha</li><li>beta</li></ul>")
    expect(html).toContain("<ol><li>one</li><li>two</li></ol>")
    expect(html).toContain("<th>Name</th><th>Value</th>")
    expect(html).toContain("<td>A</td><td>1</td>")
    expect(html).toContain("<hr>")
  })

  it("renders empty input and ordinary line breaks as paragraphs", () => {
    expect(markdownToHtml("")).toBe("<p></p>")
    expect(markdownToHtml("first\nsecond")).toBe("<p>first<br>second</p>")
  })
})
