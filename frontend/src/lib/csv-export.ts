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
