function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

export function markdownToHtml(markdown: string) {
  let html = escapeHtml(markdown || "")
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
      if (lines.every((line) => /^>\s?/.test(line.trim()))) {
        return `<blockquote>${lines.map((line) => line.replace(/^>\s?/, "")).join("<br>")}</blockquote>`
      }
      if (lines.every((line) => /^[-*]\s+/.test(line.trim()))) {
        return `<ul>${lines.map((line) => `<li>${line.replace(/^[-*]\s+/, "")}</li>`).join("")}</ul>`
      }
      if (lines.every((line) => /^\d+\.\s+/.test(line.trim()))) {
        return `<ol>${lines.map((line) => `<li>${line.replace(/^\d+\.\s+/, "")}</li>`).join("")}</ol>`
      }
      if (lines.length >= 2 && lines[0].includes("|") && /^(\|\s*:?-+:?\s*)+\|?$/.test(lines[1].trim())) {
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
  return html
}
