import { describe, expect, it } from "vitest"
import { maximumVaf } from "./variant-detail-presentation"

describe("maximumVaf", () => {
  it.each([undefined, null, [], [{ AF: null }], [{ AF: Infinity }], [{ AF: -1 }]])(
    "shows unavailable for missing or invalid measurements: %j", (value) => {
      expect(maximumVaf(value)).toBe("-")
    },
  )
  it("preserves a measured zero and selects the highest valid frequency", () => {
    expect(maximumVaf([{ AF: 0 }])).toBe("0.0%")
    expect(maximumVaf([{ AF: 0.2 }, { AF: 0.45 }, { AF: null }])).toBe("45.0%")
  })
})
