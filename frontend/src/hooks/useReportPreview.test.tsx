import type { PropsWithChildren } from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: mocks, ApiClientError: class extends Error {} }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))

import { useReportPreview } from "./useReportPreview"
import { notifySuccess } from "@/lib/notifications"

it("keeps a pending report save scoped to its original sample after navigation", async () => {
  mocks.get.mockResolvedValue({ data: { meta: { preview_fingerprint: "synthetic" } } })
  let finish!: () => void
  mocks.post.mockImplementation(() => new Promise(resolve => { finish = () => resolve({ data: {} }) }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidate = vi.spyOn(client, "invalidateQueries")
  const saved = vi.fn()
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { result, rerender } = renderHook(({ sampleId }) => useReportPreview({
    sampleId, reportType: "dna", includeSnapshot: false, pdfEnabled: false, onSaved: saved,
  }), { wrapper, initialProps: { sampleId: "SYNTHETIC-A" } })
  await waitFor(() => expect(result.current.data).toBeDefined())
  act(() => result.current.saveReport.mutate())
  await waitFor(() => expect(finish).toBeDefined())
  rerender({ sampleId: "SYNTHETIC-B" })
  await act(async () => finish())
  expect(saved).not.toHaveBeenCalled()
  expect(notifySuccess).toHaveBeenCalledWith("Report saved", expect.any(String), "Reports", expect.objectContaining({ id: "SYNTHETIC-A" }))
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["report-preview", "SYNTHETIC-A", "dna"] })
})

it("encodes sample identifiers consistently for report previews and saves", async () => {
  mocks.get.mockResolvedValue({ data: { meta: { preview_fingerprint: "synthetic" } } })
  mocks.post.mockResolvedValue({ data: {} })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useReportPreview({
    sampleId: "CASE#1?scope=test", reportType: "dna", includeSnapshot: false,
    pdfEnabled: false, onSaved: vi.fn(),
  }), { wrapper })
  await waitFor(() => expect(result.current.data).toBeDefined())
  expect(mocks.get).toHaveBeenCalledWith(
    "/samples/CASE%231%3Fscope%3Dtest/reports/dna/preview?include_snapshot=false&save=false&format=modern",
  )
  await act(async () => { await result.current.saveReport.mutateAsync() })
  expect(mocks.post).toHaveBeenCalledWith("/samples/CASE%231%3Fscope%3Dtest/reports/dna", {
    preview_fingerprint: "synthetic", report_format: "modern",
  })
})
