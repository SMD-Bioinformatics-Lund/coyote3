export function csvCellText(value: unknown): string {
  if (!Array.isArray(value)) {
    return typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "")
  }

  const seen = new Set<string>()
  return value
    .map((item) => typeof item === "object" && item !== null ? JSON.stringify(item) : String(item ?? ""))
    .filter((item) => {
      const identity = item.toLocaleLowerCase()
      if (!item || seen.has(identity)) return false
      seen.add(identity)
      return true
    })
    .join(" | ")
}

export function escapeCsvCell(value: unknown, alwaysQuote = false): string {
  let text = csvCellText(value)
  const numeric = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text.trimStart())
  if (!numeric && (/^[\t\r\n]/.test(text) || /^[\s]*[=+\-@]/.test(text))) text = `'${text}`
  return alwaysQuote || /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}
