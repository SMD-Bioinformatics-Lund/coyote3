export type TableDensity = "compact" | "standard" | "relaxed"

export function resolveTableDensity(columnCount: number, containerWidth: number): TableDensity {
  if (containerWidth <= 0) {
    if (columnCount >= 12) return "compact"
    if (columnCount >= 8) return "standard"
    return "relaxed"
  }

  const widthPerColumn = containerWidth / Math.max(1, columnCount)
  if (widthPerColumn >= 150) return "relaxed"
  if (widthPerColumn >= 120) return "standard"
  return "compact"
}

export function resolveTableMinimumWidth(columnCount: number, density: TableDensity): string {
  const sizing = {
    compact: { floor: 32, perColumn: 4.5 },
    standard: { floor: 38, perColumn: 5.5 },
    relaxed: { floor: 42, perColumn: 6.5 },
  }[density]
  return `${Math.max(sizing.floor, columnCount * sizing.perColumn)}rem`
}
