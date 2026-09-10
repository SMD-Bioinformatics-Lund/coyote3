import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/runtime-config", () => ({ runtimeConfig: {
  igvUri: "http://localhost:60151", igvDataRoot: "",
} }))

import { igvAlignmentLinks, igvLoadUrl } from "./external-links"
import { runtimeConfig } from "./runtime-config"

describe("sample alignment links", () => {
  beforeEach(() => {
    runtimeConfig.igvDataRoot = ""
  })

  it("uses the workstation root for BAM, BAI and the assay design BED", () => {
    runtimeConfig.igvDataRoot = "/R:"
    const links = igvAlignmentLinks(
      { case: ["panel/BAM/custom.bam"], control: ["panel/BAM/control.bam"] }, "17:1-2",
      { "panel/BAM/custom.bam": "panel/BAM/custom.bai" },
      ["panel/BED/design.bed"],
    )
    expect(links).toHaveLength(1)
    expect(new URL(links[0].href).searchParams.get("file")).toBe("/R:panel/BAM/custom.bam,/R:panel/BAM/control.bam,/R:panel/BED/design.bed")
    expect(new URL(links[0].href).searchParams.get("index")).toBe("/R:panel/BAM/custom.bai,,")
    expect(new URL(links[0].href).searchParams.get("locus")).toBe("17:1-2")
  })

  it("omits unconfigured design BED and avoids adding the root twice", () => {
    runtimeConfig.igvDataRoot = "/R:"
    const links = igvAlignmentLinks({ case: ["/R:tumwgs/BAM/custom.bam"] }, "17:1-2")
    expect(links).toHaveLength(1)
    expect(new URL(links[0].href).searchParams.get("file")).toBe("/R:tumwgs/BAM/custom.bam")
  })

  it("supports a configured POSIX root without inventing a drive letter", () => {
    runtimeConfig.igvDataRoot = "/mnt/alignments"
    const links = igvAlignmentLinks({ case: ["panel/BAM/custom.bam"] }, "17:1-2")
    expect(new URL(links[0].href).searchParams.get("file")).toBe("/mnt/alignments/panel/BAM/custom.bam")
  })

  it("encodes explicit paths and indexes without losing spaces or query characters", () => {
    const url = new URL(igvLoadUrl("/case reads.bam", "17:1-2", "/index & reads.bai")!)
    expect(url.searchParams.get("file")).toBe("/case reads.bam")
    expect(url.searchParams.get("index")).toBe("/index & reads.bai")
    expect(url.searchParams.get("merge")).toBe("true")
  })

  it("keeps index discovery for a role without a supplied index", () => {
    const links = igvAlignmentLinks(
      { case: ["/case.bam"], control: ["/control.bam"] }, "17:1-2",
      { "/case.bam": "/different-name.bai" },
    )
    expect(links).toHaveLength(1)
    expect(new URL(links[0].href).searchParams.get("index")).toBe("/different-name.bai,")
  })

  it("handles multiple lookup paths and omits absent or malformed targets", () => {
    expect(igvAlignmentLinks({ case: ["/a.bam", "/b.bam"] }, "1:10")).toHaveLength(1)
    expect(igvAlignmentLinks({}, "1:10")).toEqual([])
    expect(igvAlignmentLinks({ case: [null, {}] }, "1:10")).toEqual([])
    expect(igvAlignmentLinks({ case: ["/a.bam"] }, "-")).toEqual([])
    expect(igvLoadUrl({}, "1:10")).toBeNull()
  })

  it("deduplicates tracks and preserves a later explicit index association", () => {
    runtimeConfig.igvDataRoot = "/mnt"
    const links = igvAlignmentLinks(
      { case: ["a.bam", "/mnt/a.bam", "", " "] }, "1:10",
      { "/mnt/a.bam": "a.bai" }, ["design.bed", "design.bed"],
    )
    expect(links).toHaveLength(1)
    const params = new URL(links[0].href).searchParams
    expect(params.get("file")).toBe("/mnt/a.bam,/mnt/design.bed")
    expect(params.get("index")).toBe("/mnt/a.bai,")
  })
})
