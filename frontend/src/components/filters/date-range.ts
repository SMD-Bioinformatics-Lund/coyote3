export type DateRangePreset = "all" | "today" | "1d" | "3d" | "7d" | "30d" | "custom"

export const DATE_RANGE_OPTIONS = [
  { value: "all", label: "All dates" },
  { value: "today", label: "Today" },
  { value: "1d", label: "Last 24 hours" },
  { value: "3d", label: "Last 3 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "custom", label: "Custom range" },
] as const satisfies ReadonlyArray<{ value: DateRangePreset; label: string }>

const DATE_RANGE_PRESETS = new Set<DateRangePreset>(DATE_RANGE_OPTIONS.map(({ value }) => value))

export type DateRangeBounds = {
  addedFrom: string | null
  addedUntil: string | null
}

export function parseDateRangePreset(value: string | null | undefined): DateRangePreset {
  return value && DATE_RANGE_PRESETS.has(value as DateRangePreset) ? value as DateRangePreset : "all"
}

export function dateRangeLabel(preset: DateRangePreset): string {
  return DATE_RANGE_OPTIONS.find(({ value }) => value === preset)?.label ?? "All dates"
}

function localDateBoundary(value: string, nextDay = false) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split("-").map(Number)
  if (!year || !month || !day) return null
  const boundary = new Date(0)
  boundary.setFullYear(year, month - 1, day)
  boundary.setHours(0, 0, 0, 0)
  if (boundary.getFullYear() !== year || boundary.getMonth() !== month - 1 || boundary.getDate() !== day) return null
  if (nextDay) boundary.setDate(boundary.getDate() + 1)
  return Number.isNaN(boundary.getTime()) ? null : boundary.toISOString()
}

export function resolveDateRange(
  preset: DateRangePreset,
  customFrom: string,
  customUntil: string,
  now = new Date(),
): DateRangeBounds {
  if (preset === "all") return { addedFrom: null, addedUntil: null }
  if (preset === "custom") {
    return {
      addedFrom: customFrom ? localDateBoundary(customFrom) : null,
      addedUntil: customUntil ? localDateBoundary(customUntil, true) : null,
    }
  }
  if (preset === "today") {
    return {
      addedFrom: new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString(),
      addedUntil: null,
    }
  }
  const days = Number.parseInt(preset, 10)
  return {
    addedFrom: new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString(),
    addedUntil: null,
  }
}
