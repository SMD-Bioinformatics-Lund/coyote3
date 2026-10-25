import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { useDocumentEditor } from "./useDocumentEditor"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))
const response = (owned = true) => ({ status: 200, data: {
  owned, owner: "first.editor", expires_at: new Date(Date.now() + 90_000).toISOString(), renew_after_seconds: 30,
} })
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.post).mockImplementation(async () => response()) })
afterEach(() => { vi.useRealTimers() })

it("blocks saves until ownership and a fresh document have both loaded", async () => {
  let ready!: () => void
  const prepare = () => new Promise<void>((resolve) => { ready = resolve })
  const { result, unmount } = renderHook(() => useDocumentEditor("genelists", "shared", true, prepare))
  expect(result.current.owned).toBe(false)
  expect(() => result.current.options()).toThrow("not active")
  await waitFor(() => expect(ready).toBeDefined())
  await act(async () => ready())
  expect(result.current.owned).toBe(true)
  const acquire = vi.mocked(api.post).mock.calls[0]
  expect(result.current.options().headers).toEqual({ "X-Edit-Session": (acquire[1] as { editor_id: string }).editor_id })
  unmount()
  expect(api.post).toHaveBeenCalledWith("/editing/genelists/shared/release", acquire[1], { keepalive: true })
})

it("gives separate forms different sessions and keeps the losing editor read-only", async () => {
  let owner: string | undefined
  vi.mocked(api.post).mockImplementation(async (path, body) => {
    const id = (body as { editor_id: string }).editor_id
    if (path.endsWith("/acquire") && !owner) owner = id
    return response(id === owner)
  })
  const first = renderHook(() => useDocumentEditor("draft", "one", true))
  const second = renderHook(() => useDocumentEditor("draft", "one", true))
  await waitFor(() => expect(first.result.current.owned).toBe(true))
  await waitFor(() => expect(second.result.current.pending).toBe(false))
  expect(second.result.current.owned).toBe(false)
  expect(second.result.current.owner).toBe("first.editor")
  expect(() => second.result.current.options()).toThrow("not active")
})

it("fails closed when renewal fails", async () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useDocumentEditor("draft", "one", true))
  await act(async () => { await Promise.resolve() })
  expect(result.current.owned).toBe(true)
  vi.mocked(api.post).mockImplementation(async (path) => {
    if (path.endsWith("/renew")) throw new Error("Editing permission revoked")
    return response()
  })
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
  expect(result.current.owned).toBe(false)
  expect(result.current.error).toBe("Editing permission revoked")
  expect(() => result.current.options()).toThrow("not active")
})

it("rejects expiry before a suspended tab's renewal timer fires", async () => {
  const { result } = renderHook(() => useDocumentEditor("draft", "one", true))
  await waitFor(() => expect(result.current.owned).toBe(true))
  const now = Date.now()
  vi.spyOn(Date, "now").mockReturnValue(now + 91_000)
  expect(() => result.current.options()).toThrow("not active")
  vi.restoreAllMocks()
})

it("does not acquire locks for read-only or unsaved documents", () => {
  const { result } = renderHook(() => useDocumentEditor("draft", "", false))
  expect(result.current.options()).toEqual({})
  expect(api.post).not.toHaveBeenCalled()
})
