import { describe, expect, it } from "vitest"
import { fieldLabel, titleize } from "./resource-list"
import { specs } from "./resource-specs"

describe("Clinical resource terminology", () => {
  it.each([
    ["asp_id", "Assay ID"],
    ["asp_ids", "Assays"],
    ["asp_group", "Assay group"],
    ["asp_category", "Assay category"],
    ["asp_family", "Assay family"],
    ["aspc_id", "Configuration ID"],
    ["isgl_id", "Gene list ID"],
  ])("labels %s without changing its technical key", (key, label) => {
    expect(titleize(key)).toBe(label)
    expect(fieldLabel(key)).toBe(label)
  })

  it("keeps assay routes and permissions unchanged", () => {
    expect(specs.asp.title).toBe("Assays")
    expect(specs.asp.endpoint).toBe("/resources/asp")
    expect(specs.asp.permissions.view).toBe("assay.panel:view")
  })
})
