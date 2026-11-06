import { describe, expect, it } from "vitest"
import { coord, coverageNumber } from "./coverage-presentation"

describe("coverage measurements", () => {
  it.each([null, undefined, "", " "])("does not classify missing coverage %s as zero depth", cov => {
    expect(coverageNumber({ cov })).toBeNaN()
  })

  it("preserves measured zero depth and zero-based genomic coordinates", () => {
    expect(coverageNumber({ cov: 0 })).toBe(0)
    expect(coord({ chr: "1", start: 0, end: 100 })).toBe("1:0-100")
  })
})
