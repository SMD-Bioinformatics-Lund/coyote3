

export function labelText(value: unknown) {
  const text = String(value || "-").trim()
  if (text.toLowerCase() === "base") return "Assay-wide"
  return text.replaceAll("_", " ").replaceAll("-", " ")
}

export function uniqueOptions(values: string[]) {
  return Array.from(new Set(values.filter((value) => value && value !== "-"))).sort((a, b) => a.localeCompare(b))
}

export function contiguousSpans<T>(
  items: T[],
  keyFn: (item: T) => string,
  labelFn: (item: T) => string = keyFn,
) {
  const spans: Array<{ key: string; label: string; span: number }> = []
  for (const item of items) {
    const key = keyFn(item)
    const label = labelFn(item)
    const last = spans[spans.length - 1]
    if (last?.key === key) last.span += 1
    else spans.push({ key, label, span: 1 })
  }
  return spans
}

export function matrixBoundaryClass(columns: any[], index: number) {
  if (index <= 0) return ""
  const previous = columns[index - 1]
  const current = columns[index]
  if (previous?.mod !== current?.mod) return "matrix-section"
  if (`${previous?.mod}::${previous?.assayGroup}` !== `${current?.mod}::${current?.assayGroup}`) {
    return "matrix-group"
  }
  return ""
}

export function matrixBoundaryStyle(boundary: string) {
  if (boundary === "matrix-section") {
    return {
      boxShadow: "inset 2px 0 0 var(--paper-edge)",
    }
  }
  if (boundary === "matrix-group") {
    return {
      boxShadow: "inset 1px 0 0 var(--paper-edge)",
    }
  }
  return undefined
}

export function matrixModalityLabel(label: string) {
  if (/\bWGS\b|whole[ -]genome sequencing/i.test(label)) return "WGS"
  if (/\bWTS\b|whole[ -]transcriptome sequencing/i.test(label)) return "WTS"
  return labelText(label)
}

export function matrixColumnWidth(label: unknown) {
  const words = String(label || "-")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  const longestWordLength = Math.max(3, ...words.map((word) => word.length))

  // Matrix cells contain only a check mark or dash. Size each column for its
  // longest header word, then let multi-word labels wrap at their spaces.
  return Math.min(96, Math.max(48, longestWordLength * 5.4 + 14))
}
