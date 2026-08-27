export function isPresent(value: unknown) {
  if (value === null || value === undefined) return false
  if (typeof value === "string") return value.trim() !== "" && value !== "-"
  if (Array.isArray(value)) return value.length > 0
  return true
}

export function displayValue(value: unknown, fallback = "-") {
  if (!isPresent(value)) return fallback
  if (Array.isArray(value)) return value.filter(isPresent).join(", ") || fallback
  if (typeof value === "boolean") return value ? "Yes" : "No"
  return String(value)
}

export function percentValue(value: unknown, digits = 2) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "-"
  return `${(numeric * 100).toFixed(digits)}%`
}

export function shortCount(value: unknown, fallback = "0") {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  const abs = Math.abs(numeric)
  const sign = numeric < 0 ? "-" : ""
  const units: Array<[number, string]> = [
    [1_000_000_000, "B"],
    [1_000_000, "M"],
    [1_000, "K"],
  ]
  const unit = units.find(([size]) => abs >= size)
  if (!unit) return String(numeric)
  const [size, suffix] = unit
  const compact = (abs / size).toFixed(abs >= size * 10 ? 0 : 1).replace(/\.0$/, "")
  return `${sign}${compact}${suffix}`
}

const configuredLocalTimeZone = String(runtimeConfig.localTimeZone || "").trim()

export function localTimeZone() {
  if (!configuredLocalTimeZone) {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
  }
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: configuredLocalTimeZone }).format(new Date())
    return configuredLocalTimeZone
  } catch {
    return "UTC"
  }
}

export function utcDate(value: unknown) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === "number") {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
  }

  const raw = String(value).trim()
  if (!raw) return null
  const normalized = /^\d{4}-\d{2}-\d{2}[T ][\d:.]+$/.test(raw) ? `${raw.replace(" ", "T")}Z` : raw
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function fullDateTime(value: unknown, fallback = "-") {
  const date = utcDate(value)
  if (!date) return value ? String(value) : fallback
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: localTimeZone(),
  }).format(date)
}

export function localDate(value: unknown, fallback = "-") {
  const date = utcDate(value)
  if (!date) return value ? String(value) : fallback
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: localTimeZone(),
  }).format(date)
}

export function humanRelativeDate(value: unknown, fallback = "-") {
  const date = utcDate(value)
  if (!date) return value ? String(value) : fallback

  const diffMs = Date.now() - date.getTime()
  const absMs = Math.abs(diffMs)
  const suffix = diffMs >= 0 ? "ago" : "from now"
  const units: Array<[number, string]> = [
    [365 * 24 * 60 * 60 * 1000, "yr"],
    [30 * 24 * 60 * 60 * 1000, "mo"],
    [24 * 60 * 60 * 1000, "d"],
    [60 * 60 * 1000, "h"],
    [60 * 1000, "min"],
  ]
  const unit = units.find(([size]) => absMs >= size)
  if (!unit) return "just now"
  const [size, label] = unit
  return `${Math.round(absMs / size)} ${label} ${suffix}`
}
import { runtimeConfig } from "@/lib/runtime-config"
