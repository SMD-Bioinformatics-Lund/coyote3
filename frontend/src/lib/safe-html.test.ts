import { describe, expect, it } from "vitest"
import { sanitizeRichText } from "./safe-html"

describe("sanitizeRichText", () => {
  it("preserves formatting and reference links", () => {
    const source = '<p><strong>Finding</strong> H<sub>2</sub><a href="https://example.org" title="Reference">Source</a></p>'
    expect(sanitizeRichText(source)).toBe(source)
  })

  it.each([
    '<img src=x onerror="alert(1)">',
    '<svg onload="alert(1)"></svg>',
    '<script>alert(1)</script>',
    '<iframe srcdoc="bad"></iframe>',
    '<a href="javascript:alert(1)" onclick="alert(1)">Link</a>',
    '<a href="jav&#x61;script:alert(1)">Link</a>',
    '<div style="background:url(https://example.org/tracker)">Text</div>',
    '<form action="/api/v1/users"><input name="role" value="admin"></form>',
  ])("removes active content from %s", (source) => {
    expect(sanitizeRichText(source)).not.toMatch(/<img|<svg|<script|<iframe|<form|<input|onclick|onerror|onload|javascript:|style=/i)
  })
})
