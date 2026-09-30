import DOMPurify from "dompurify"

/** Preserve document formatting without active content or embedded resources. */
export function sanitizeRichText(value: string): string {
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS: [
      "p", "br", "strong", "em", "b", "i", "u", "sub", "sup", "ul", "ol", "li",
      "code", "pre", "blockquote", "a", "table", "thead", "tbody", "tr", "th", "td",
      "div", "span", "h2", "h3", "h4", "hr",
    ],
    ALLOWED_ATTR: ["href", "title", "colspan", "rowspan"],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
  })
}
