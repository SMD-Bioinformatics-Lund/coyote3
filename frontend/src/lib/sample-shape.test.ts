import { describe, expect, it } from "vitest"

import {
  activeFilterSectionForTab,
  hasSampleFile,
  mergeSampleFilterSection,
  sampleFileName,
  sampleFilePath,
  sampleFilterSection,
  sampleReported,
  sampleSubpanel,
} from "./sample-shape"

describe("sample shape helpers", () => {
  it("reads string and structured file records across path styles", () => {
    const sample = {
      files: {
        vcf: "/data/case.vcf",
        cnv: { path: "C:\\data\\case.cnv.json" },
        empty: "",
      },
    }

    expect(sampleFilePath(sample, "vcf")).toBe("/data/case.vcf")
    expect(sampleFileName(sample, "cnv")).toBe("case.cnv.json")
    expect(hasSampleFile(sample, "vcf")).toBe(true)
    expect(hasSampleFile(sample, "empty")).toBe(false)
    expect(sampleFileName(sample, "missing")).toBeUndefined()
  })

  it("normalizes sample metadata and report state", () => {
    expect(sampleSubpanel({ subpanel_id: "myeloid" })).toBe("myeloid")
    expect(sampleSubpanel({})).toBeUndefined()
    expect(sampleReported({ reported: true })).toBe(true)
    expect(sampleReported({ latest_report_id: "report-1" })).toBe(true)
    expect(sampleReported({})).toBe(false)
  })

  it("reads and immutably merges intent-specific filter sections", () => {
    const sample = {
      filters: {
        somatic: { snv: { min_depth: 100 }, cnv: { min_size: 5 } },
        germline: { snv: { min_depth: 30 } },
      },
    }

    expect(sampleFilterSection(sample, "snv")).toEqual({ min_depth: 100 })
    expect(sampleFilterSection(sample, "snv", "germline")).toEqual({ min_depth: 30 })
    expect(sampleFilterSection({ somatic: { snv: [] } }, "snv")).toEqual({})

    const merged = mergeSampleFilterSection(sample, "snv", { min_depth: 250 })
    expect(merged.somatic).toEqual({ snv: { min_depth: 250 }, cnv: { min_size: 5 } })
    expect(merged.germline).toEqual({ snv: { min_depth: 30 } })
    expect(sample.filters.somatic.snv).toEqual({ min_depth: 100 })
  })

  it.each([
    ["snvs", "snv"],
    ["germline-snvs", "snv"],
    ["cnvs", "cnv"],
    ["coverage", "coverage"],
    ["fusions", "fusion"],
    ["overview", null],
  ])("maps the %s tab to its filter section", (tab, expected) => {
    expect(activeFilterSectionForTab(tab)).toBe(expected)
  })
})
