import { describe, expect, it } from "vitest"

import { displayValue, isPresent, percentValue, shortCount, utcDate } from "./detail-formatters"

describe("detail formatters", () => {
  it("distinguishes absent values from valid false and zero values", () => {
    expect(isPresent(null)).toBe(false)
    expect(isPresent("-")).toBe(false)
    expect(isPresent([])).toBe(false)
    expect(isPresent(false)).toBe(true)
    expect(isPresent(0)).toBe(true)
  })

  it("formats scalar and collection display values", () => {
    expect(displayValue(false)).toBe("No")
    expect(displayValue(true)).toBe("Yes")
    expect(displayValue(["TP53", "", null, "KRAS"])).toBe("TP53, KRAS")
    expect(displayValue(undefined, "N/A")).toBe("N/A")
  })

  it("formats percentages and compact counts", () => {
    expect(percentValue(0.12345, 1)).toBe("12.3%")
    expect(percentValue("invalid")).toBe("-")
    expect(shortCount(999)).toBe("999")
    expect(shortCount(1_420)).toBe("1.4K")
    expect(shortCount(15_000)).toBe("15K")
    expect(shortCount(-2_100_000)).toBe("-2.1M")
  })

  it("treats timestamps without an offset as UTC", () => {
    expect(utcDate("2026-07-31 12:30:00")?.toISOString()).toBe("2026-07-31T12:30:00.000Z")
    expect(utcDate("not-a-date")).toBeNull()
  })
})
