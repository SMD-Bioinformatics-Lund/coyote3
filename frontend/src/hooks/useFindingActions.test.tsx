import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  applyFindingAction: vi.fn(),
  setSingleFlag: vi.fn(),
  notifySuccess: vi.fn(),
  notifyActionError: vi.fn(),
}))

vi.mock("@/lib/finding-actions", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/finding-actions")>()
  return { ...actual, applyFindingAction: mocks.applyFindingAction, setSingleFlag: mocks.setSingleFlag }
})
vi.mock("@/lib/notifications", () => ({
  notifySuccess: mocks.notifySuccess,
  notifyActionError: mocks.notifyActionError,
}))

import { useBulkFindingAction, useSingleFindingFlag } from "./useFindingActions"

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidate = vi.spyOn(client, "invalidateQueries")
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, invalidate, wrapper }
}

describe("finding action hooks", () => {
  beforeEach(() => vi.clearAllMocks())

  it("applies a bulk action, invalidates clinical caches, and notifies the user", async () => {
    mocks.applyFindingAction.mockResolvedValue({ ok: true })
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(() => useBulkFindingAction("S1", "small_variant"), { wrapper })

    await act(() => result.current.mutateAsync({ action: "tier_2", resourceIds: ["V1", "V2"] }))

    expect(mocks.applyFindingAction).toHaveBeenCalledWith({
      sampleId: "S1", resourceType: "small_variant", action: "tier_2", resourceIds: ["V1", "V2"],
    })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["sample-variants", "S1"] })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["sample-comment-suggestion", "S1"] })
    expect(mocks.notifySuccess).toHaveBeenCalledWith(
      "Finding action applied", "tier_2 was applied to 2 selected item(s).", "small_variant",
    )
  })

  it("reports bulk action failures without showing success", async () => {
    const error = new Error("denied")
    mocks.applyFindingAction.mockRejectedValue(error)
    const { wrapper } = setup()
    const { result } = renderHook(() => useBulkFindingAction("S1", "cnv"), { wrapper })

    await expect(act(() => result.current.mutateAsync({ action: "fp", resourceIds: ["C1"] }))).rejects.toThrow("denied")
    await waitFor(() => expect(mocks.notifyActionError).toHaveBeenCalledWith("Unable to apply finding action", error, "cnv"))
    expect(mocks.notifySuccess).not.toHaveBeenCalled()
  })

  it("sets and removes a single flag with the correct notification", async () => {
    mocks.setSingleFlag.mockResolvedValue({ ok: true })
    const { wrapper } = setup()
    const { result } = renderHook(() => useSingleFindingFlag("S2", "fusion"), { wrapper })

    await act(() => result.current.mutateAsync({ resourceId: "F1", flag: "interesting", apply: false }))

    expect(mocks.setSingleFlag).toHaveBeenCalledWith({
      sampleId: "S2", resourceType: "fusion", resourceId: "F1", flag: "interesting", apply: false,
    })
    expect(mocks.notifySuccess).toHaveBeenCalledWith("Flag removed", "interesting was removed.", "fusion")
  })
})
