import { describe, expect, it } from "vitest"

import {
  GENELIST_TYPE_METADATA,
  configuredValueDescription,
} from "./configured-values"

describe("configured value metadata", () => {
  it("defines descriptions and semantic badge classes for every gene-list type", () => {
    expect(Object.keys(GENELIST_TYPE_METADATA)).toEqual([
      "snv",
      "cnv",
      "fusion",
      "expression",
      "pgx",
      "adhoc_snv",
      "adhoc_cnv",
      "adhoc_fusion",
      "adhoc_expression",
      "adhoc_pgx",
    ])
    for (const metadata of Object.values(GENELIST_TYPE_METADATA)) {
      expect(metadata.description.length).toBeGreaterThan(20)
      expect(metadata.className).toMatch(/^badge-/)
    }
  })

  it("looks values up case-insensitively and returns empty text for unknown values", () => {
    expect(configuredValueDescription("SNV")).toContain("small-variant")
    expect(configuredValueDescription("adhoc_pgx")).toContain("Temporary")
    expect(configuredValueDescription("unknown")).toBe("")
    expect(configuredValueDescription("")).toBe("")
  })
})
