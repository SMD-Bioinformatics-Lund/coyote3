import { describe, expect, it } from "vitest"

import { sampleDetailPath, sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "./sample-routing"

describe("sample routing", () => {
  it("prefers the human-readable sample name", () => {
    expect(sampleUrlKey({ name: "sample 01", _id: "opaque-id" })).toBe("sample%2001")
    expect(sampleDetailPath({ sample_name: "rna/01" })).toBe("/samples/rna%2F01")
  })

  it("uses explicit fallbacks before object identifiers", () => {
    expect(sampleUrlKey({ _id: "opaque-id" }, "fallback-name")).toBe("fallback-name")
    expect(sampleUrlKey({ id: "id-value" })).toBe("id-value")
  })

  it("builds tab and finding links with encoded values", () => {
    const sample = { name: "sample-01" }
    expect(sampleDetailTabPath(sample, undefined, "somatic snvs")).toBe(
      "/samples/sample-01?tab=somatic%20snvs",
    )
    expect(sampleFindingPath(sample, undefined, "variant", "var/1")).toBe(
      "/samples/sample-01/variant/var%2F1",
    )
  })
})
