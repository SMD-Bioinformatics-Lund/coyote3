function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

const ESCAPABLE_MARKDOWN_CHARACTERS = new Set([
  "\\",
  "`",
  "*",
  "_",
  "[",
  "]",
  "{",
  "}",
  "(",
  ")",
  "#",
  "+",
  "-",
  ".",
  "!",
  ">",
  "|",
  "~",
])

function protectEscapedMarkdown(value: string) {
  const escaped: string[] = []
  let protectedValue = ""
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index]
    const next = value[index + 1]
    if (character === "\\" && next && ESCAPABLE_MARKDOWN_CHARACTERS.has(next)) {
      protectedValue += `@@COYOTE_ESC_${escaped.push(next) - 1}@@`
      index += 1
      continue
    }
    protectedValue += character
  }
  return {
    escaped,
    value: protectedValue,
  }
}

function restoreEscapedMarkdown(value: string, escaped: string[]) {
  return value.replace(/@@COYOTE_ESC_(\d+)@@/g, (_match, index: string) => (
    escapeHtml(escaped[Number(index)] || "")
  ))
}

export function markdownToHtml(markdown: string) {
  const protectedMarkdown = protectEscapedMarkdown(markdown || "")
  let html = escapeHtml(protectedMarkdown.value)
  html = html.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>")
  html = html.replace(/^######\s+(.+)$/gm, "<h6>$1</h6>")
  html = html.replace(/^#####\s+(.+)$/gm, "<h5>$1</h5>")
  html = html.replace(/^####\s+(.+)$/gm, "<h4>$1</h4>")
  html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>")
  html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>")
  html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>")
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>")
  html = html.replace(/~~([^~]+)~~/g, "<del>$1</del>")
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
  html = html
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n")
      if (lines.every((line) => /^&gt;\s?/.test(line.trim()))) {
        return `<blockquote>${lines.map((line) => line.replace(/^&gt;\s?/, "")).join("<br>")}</blockquote>`
      }
      if (lines.every((line) => /^[-*]\s+/.test(line.trim()))) {
        return `<ul>${lines.map((line) => `<li>${line.replace(/^[-*]\s+/, "")}</li>`).join("")}</ul>`
      }
      if (lines.every((line) => /^\d+\.\s+/.test(line.trim()))) {
        return `<ol>${lines.map((line) => `<li>${line.replace(/^\d+\.\s+/, "")}</li>`).join("")}</ol>`
      }
      if (
        lines.length >= 2
        && lines[0].includes("|")
        && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(lines[1].trim())
      ) {
        const cells = (line: string) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim())
        const header = cells(lines[0])
        const rows = lines.slice(2).filter(Boolean).map(cells)
        return `<table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      }
      if (lines.length === 1 && /^-{3,}$/.test(lines[0].trim())) {
        return "<hr>"
      }
      return `<p>${block.replace(/\n/g, "<br>")}</p>`
    })
    .join("")
  return restoreEscapedMarkdown(html, protectedMarkdown.escaped)
}
