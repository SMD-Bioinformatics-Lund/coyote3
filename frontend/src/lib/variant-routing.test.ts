import { describe, expect, it } from "vitest"

import { tieredVariantSearchPath, tieredVariantSearchState } from "./variant-routing"

describe("tiered variant search routing", () => {
  it("builds a gene search scoped to the sample assay group", () => {
    expect(tieredVariantSearchPath("HLA-B", "hematology")).toBe(
      "/variants/search?search_str=HLA-B&search_mode=gene&assays=hematology",
    )
  })

  it("hydrates and normalizes tiered-search URL state", () => {
    const params = new URLSearchParams(
      "search_str=TP53&search_mode=gene&assays=solid&assays=solid&include_annotation_text=true",
    )

    expect(tieredVariantSearchState(params)).toEqual({
      search: "TP53",
      mode: "gene",
      includeText: true,
      assays: ["solid"],
    })
  })
})
