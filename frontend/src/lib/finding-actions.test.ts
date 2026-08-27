import { beforeEach, describe, expect, it, vi } from "vitest"

const apiMock = vi.hoisted(() => ({
  patch: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}))

vi.mock("@/lib/api", () => ({ api: apiMock }))

import {
  applyFindingAction,
  findingBulkActionOptions,
  findingQueryKeys,
  setSingleFlag,
} from "./finding-actions"

describe("finding actions", () => {
  beforeEach(() => {
    apiMock.patch.mockReset().mockResolvedValue({ data: {}, status: 200 })
    apiMock.post.mockReset().mockResolvedValue({ data: {}, status: 200 })
    apiMock.delete.mockReset().mockResolvedValue({ data: {}, status: 200 })
  })

  it("returns every query cache family affected by a mutation", () => {
    expect(findingQueryKeys("sample-1", "small_variant")).toEqual([
      ["sample", "sample-1"],
      ["sample-variants", "sample-1"],
      ["variants", "sample-1"],
    ])
    expect(findingQueryKeys("sample-1", "cnv")).toContainEqual(["sample-cnvs", "sample-1"])
    expect(findingQueryKeys("sample-1", "fusion")).toContainEqual(["fusions", "sample-1"])
    expect(findingQueryKeys("sample-1", "translocation")).toContainEqual([
      "translocations",
      "sample-1",
    ])
  })

  it("builds resource-specific bulk action catalogs from shared definitions", () => {
    const snvActions = findingBulkActionOptions("small_variant")
    const fusionActions = findingBulkActionOptions("fusion")
    const cnvActions = findingBulkActionOptions("cnv")

    expect(snvActions).toContainEqual({ value: "tier_1", label: "Classify as Tier 1" })
    expect(snvActions).toContainEqual({ value: "blacklist", label: "Add to Blacklist" })
    expect(fusionActions).toContainEqual({ value: "blacklisted", label: "Mark Blacklisted" })
    expect(fusionActions.some(({ value }) => value === "blacklist")).toBe(false)
    expect(cnvActions).toContainEqual({ value: "interesting", label: "Include in report" })
    expect(cnvActions.some(({ value }) => value.startsWith("tier_"))).toBe(false)
  })

  it("adds tier actions only when the resource switch enables them", () => {
    expect(
      findingBulkActionOptions("cnv", { tieringEnabled: true }),
    ).toContainEqual({ value: "tier_1", label: "Classify as Tier 1" })
    expect(
      findingBulkActionOptions("translocation", { tieringEnabled: false })
        .some(({ value }) => value.startsWith("tier_")),
    ).toBe(false)
  })

  it("ignores empty selections and applies or removes tiers in bulk", async () => {
    await expect(
      applyFindingAction({ sampleId: "sample-1", resourceType: "small_variant", action: "tier_3", resourceIds: [] }),
    ).resolves.toBeUndefined()
    expect(apiMock.patch).not.toHaveBeenCalled()

    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "small_variant",
      action: "remove_tier_2",
      resourceIds: ["", "variant-1"],
    })
    expect(apiMock.patch).toHaveBeenCalledWith("/samples/sample-1/classifications/tier", {
      resource_type: "small_variant",
      resource_ids: ["variant-1"],
      tier: 2,
      apply: false,
    })
  })

  it("uses the bulk small-variant flag endpoint", async () => {
    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "small_variant",
      action: "fp",
      resourceIds: ["variant-1", "variant-2"],
    })
    expect(apiMock.patch).toHaveBeenCalledWith(
      "/samples/sample-1/small-variants/flags/false-positive",
      { resource_ids: ["variant-1", "variant-2"], apply: true },
    )
  })

  it("encodes fusion identifiers into its bulk flag query", async () => {
    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "fusion",
      action: "relevant",
      resourceIds: ["fusion 1", "fusion/2"],
    })
    expect(apiMock.patch).toHaveBeenCalledWith(
      "/samples/sample-1/fusions/flags/irrelevant?apply=false&fusion_ids=fusion+1&fusion_ids=fusion%2F2",
    )

    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "fusion",
      action: "blacklisted",
      resourceIds: ["fusion 1"],
    })
    expect(apiMock.patch).toHaveBeenCalledWith(
      "/samples/sample-1/fusions/flags/blacklisted?apply=true&fusion_ids=fusion+1",
    )
  })

  it("applies fusion tiers through the shared classification endpoint", async () => {
    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "fusion",
      action: "tier_2",
      resourceIds: ["fusion-1", "fusion-2"],
    })

    expect(apiMock.patch).toHaveBeenCalledWith("/samples/sample-1/classifications/tier", {
      resource_type: "fusion",
      resource_ids: ["fusion-1", "fusion-2"],
      tier: 2,
      apply: true,
    })
  })

  it("applies CNV flags individually and chooses PATCH or DELETE by state", async () => {
    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "cnv",
      action: "irrelevant",
      resourceIds: ["cnv-1", "cnv-2"],
    })
    expect(apiMock.patch).toHaveBeenCalledTimes(2)
    expect(apiMock.patch).toHaveBeenCalledWith(
      "/samples/sample-1/cnvs/cnv-1/flags/irrelevant",
    )

    await setSingleFlag({
      sampleId: "sample-1",
      resourceType: "cnv",
      resourceId: "cnv-1",
      flag: "interesting",
      apply: false,
    })
    expect(apiMock.delete).toHaveBeenCalledWith(
      "/samples/sample-1/cnvs/cnv-1/flags/interesting",
    )
  })

  it("routes noteworthy, blacklist, and override actions to their canonical endpoints", async () => {
    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "translocation",
      action: "noteworthy",
      resourceIds: ["tl-1"],
    })
    expect(apiMock.patch).toHaveBeenCalledWith(
      "/samples/sample-1/translocations/tl-1/flags/noteworthy",
    )

    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "small_variant",
      action: "blacklist",
      resourceIds: ["variant-1"],
    })
    expect(apiMock.post).toHaveBeenCalledWith(
      "/samples/sample-1/small-variants/variant-1/blacklist-entries",
      {},
    )

    await applyFindingAction({
      sampleId: "sample-1",
      resourceType: "small_variant",
      action: "clear_override_blacklist",
      resourceIds: ["variant-1"],
    })
    expect(apiMock.delete).toHaveBeenCalledWith(
      "/samples/sample-1/small-variants/variant-1/flags/override-blacklist",
    )
  })
})
