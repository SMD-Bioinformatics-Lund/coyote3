import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { catalogPriceIssue, catalogPreviewIssue, useCatalogDraftPreview } from "./useCatalogDraftPreview"
import type { Catalog } from "./catalog-types"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))
const catalog: Catalog = { header: "Synthetic catalog", description: "", layout: { order: ["dna"] },
  modalities: { dna: { label: "DNA", omics: "dna", categories: {
    mpn: { label: "MPN", asp_id: "synthetic", aspc_id: "synthetic-mpn" },
  } } },
}
const publication = { version: 1, header: "Synthetic catalog", description: "", navigation: [], offerings: [] }
function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

it("does not send half-entered prices, clears stale coverage and resumes after completion", async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockResolvedValue({ data: publication, status: 200 })
  const { result, rerender } = renderHook(({ value }) => useCatalogDraftPreview(value), {
    initialProps: { value: catalog }, wrapper: createWrapper(),
  })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(api.post).toHaveBeenCalledTimes(1)
  const unfinished = structuredClone(catalog)
  unfinished.modalities.dna.categories.mpn.price = { amount: "", currency: "", kind: "fixed", conditions: "" }
  rerender({ value: unfinished })
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
  expect(result.current.issue).toContain("Complete or cancel the price edit for MPN")
  expect(result.current.data).toBeUndefined()
  expect(api.post).toHaveBeenCalledTimes(1)
  expect(catalogPriceIssue(unfinished)).toBeTruthy()
  const complete = structuredClone(unfinished)
  complete.modalities.dna.categories.mpn.price = { amount: "450", currency: "SEK", kind: "fixed", conditions: "" }
  rerender({ value: complete })
  expect(result.current.data).toBeUndefined()
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
  expect(api.post).toHaveBeenCalledTimes(2)
  expect(api.post).toHaveBeenLastCalledWith("/admin/assay-catalog/preview/offerings",
    { document: complete }, expect.objectContaining({ errorNotice: "inline", signal: expect.any(AbortSignal) }))
  expect(result.current.issue).toBeUndefined()
  expect(catalogPriceIssue(complete)).toBeUndefined()
})

it("pauses for an empty section and unfinished source links without discarding the draft", async () => {
  vi.useFakeTimers()
  const empty = structuredClone(catalog)
  empty.modalities.extra = { label: "New section", categories: {} }
  const { result, rerender } = renderHook(({ value }) => useCatalogDraftPreview(value), {
    initialProps: { value: empty }, wrapper: createWrapper(),
  })
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
  expect(result.current.issue).toContain("Add an entry or subsection to New section")
  expect(api.post).not.toHaveBeenCalled()
  const entry = structuredClone(empty)
  entry.modalities.extra.categories.new = { label: "New entry" }
  rerender({ value: entry })
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
  expect(result.current.issue).toContain("Link an assay and production configuration for New entry")
  expect(api.post).not.toHaveBeenCalled()
  expect(entry.modalities.extra.categories.new.label).toBe("New entry")
})

it("handles server validation inline and supports an explicit retry", async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockRejectedValueOnce(Object.assign(new Error("Unmatched production source"), { status: 422 }))
    .mockResolvedValue({ data: publication, status: 200 })
  const { result } = renderHook(() => useCatalogDraftPreview(catalog), { wrapper: createWrapper() })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(result.current.canRetry).toBe(true)
  expect(result.current.issue).toContain("production configuration")
  expect(result.current.data).toBeUndefined()
  expect(api.post).toHaveBeenCalledTimes(1)
  await act(async () => { result.current.retry(); await vi.advanceTimersByTimeAsync(20) })
  expect(result.current.issue).toBeUndefined()
  expect(result.current.canRetry).toBe(false)
  expect(result.current.data).toEqual(publication)
})

it("retains the draft and distinguishes a service failure from invalid source selections", async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockRejectedValue(Object.assign(new Error("Unavailable"), { status: 503 }))
  const { result } = renderHook(() => useCatalogDraftPreview(catalog), { wrapper: createWrapper() })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(result.current.issue).toContain("Your changes are retained")
  expect(result.current.issue).not.toContain("production configuration")
  expect(result.current.canRetry).toBe(true)
  expect(result.current.data).toBeUndefined()
})

it("clears an old preview failure while a changed draft is waiting for its preview", async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockRejectedValueOnce(Object.assign(new Error("Invalid source"), { status: 422 }))
    .mockResolvedValue({ data: publication, status: 200 })
  const { result, rerender } = renderHook(({ value }) => useCatalogDraftPreview(value), {
    initialProps: { value: catalog }, wrapper: createWrapper(),
  })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(result.current.issue).toContain("production configuration")
  rerender({ value: { ...catalog, description: "Updated wording" } })
  expect(result.current.pending).toBe(true)
  expect(result.current.issue).toBeUndefined()
  expect(result.current.canRetry).toBe(false)
  await act(async () => { await vi.advanceTimersByTimeAsync(400) })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(result.current.data).toEqual(publication)
})

it("accepts inherited source bindings and allows unfinished display folders", () => {
  const draft = structuredClone(catalog)
  draft.modalities.dna.categories.folder = { label: "Shared", node_kind: "folder" }
  draft.modalities.dna.categories.child = { label: "Child", parent_key: "mpn" }
  expect(catalogPreviewIssue(draft)).toBeUndefined()
})
