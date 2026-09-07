import { describe, expect, it, vi } from "vitest"

vi.mock("@/lib/runtime-config", () => ({ runtimeConfig: { igvUri: "http://localhost:60151" } }))

import { igvAlignmentLinks, igvLoadUrl } from "./external-links"

describe("sample alignment links", () => {
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
    expect(links).toHaveLength(2)
    expect(new URL(links[0].href).searchParams.get("index")).toBe("/different-name.bai")
    expect(new URL(links[1].href).searchParams.has("index")).toBe(false)
    expect(links[1].label).toContain("control")
  })

  it("handles multiple lookup paths and omits absent or malformed targets", () => {
    expect(igvAlignmentLinks({ case: ["/a.bam", "/b.bam"] }, "1:10")).toHaveLength(2)
    expect(igvAlignmentLinks({}, "1:10")).toEqual([])
    expect(igvAlignmentLinks({ case: [null, {}] }, "1:10")).toEqual([])
    expect(igvAlignmentLinks({ case: ["/a.bam"] }, "-")).toEqual([])
    expect(igvLoadUrl({}, "1:10")).toBeNull()
  })
})
