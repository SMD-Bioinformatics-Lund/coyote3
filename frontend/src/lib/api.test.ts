import { beforeEach, describe, expect, it, vi } from "vitest"

const notifyMock = vi.hoisted(() => vi.fn())

vi.mock("@/components/notifications/notification-store", () => ({ notify: notifyMock }))

import {
  ApiClientError,
  api,
  setCsrfToken,
} from "./api"

function response(body: string, status = 200, statusText = "OK") {
  return new Response(body, { status, statusText, headers: { "Content-Type": "application/json" } })
}

describe("typed API client", () => {
  beforeEach(() => {
    notifyMock.mockReset()
    vi.stubGlobal("window", { location: { pathname: "/samples", href: "/samples" } })
    vi.stubGlobal("fetch", vi.fn())
    setCsrfToken(null)
  })

  it("sends typed JSON requests and parses success and empty responses", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response('{"payload":{"id":1}}'))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))

    await expect(api.post<{ payload: { id: number } }>("/records", { name: "test" })).resolves.toEqual({
      data: { payload: { id: 1 } },
      status: 200,
    })
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe("/api/v1/records")
    expect(options).toEqual(expect.objectContaining({ method: "POST", body: '{"name":"test"}' }))
    expect(new Headers(options?.headers).get("Content-Type")).toBe("application/json")
    await expect(api.delete("/records/1")).resolves.toEqual({ data: {}, status: 204 })
  })

  it("does not force a JSON content type for form data", async () => {
    vi.mocked(fetch).mockResolvedValue(response("{}"))
    const form = new FormData()
    form.append("name", "sample")

    await api.post("/upload", form)

    const options = vi.mocked(fetch).mock.calls[0][1] as RequestInit
    expect(options.body).toBe(form)
    expect(new Headers(options.headers).has("Content-Type")).toBe(false)
  })

  it("keeps the CSRF token in memory and sends it only on mutations", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response("{}"))
      .mockResolvedValueOnce(response("{}"))
    setCsrfToken("csrf-token")

    await api.get("/records")
    await api.patch("/records/1", { name: "updated" })

    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false)
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get("X-CSRF-Token")).toBe("csrf-token")
    expect(sessionStorage.length).toBe(0)
  })

  it.each([
    [403, '{"error":"hidden"}', "You do not have permission", "warning"],
    [404, '{"error":"Sample not found"}', "Sample not found", "warning"],
    [409, '{"message":"Already exists"}', "Already exists", "warning"],
    [422, '{"error":"Invalid payload","details":"name is required"}', "Invalid payload: name is required", "warning"],
    [500, '{"error":"Internal error","details":"database unavailable"}', "The server could not complete the request: database unavailable", "error"],
  ])("converts HTTP %s responses into actionable client errors", async (status, body, message, tone) => {
    vi.mocked(fetch).mockResolvedValue(response(body, status, "Failure"))

    const promise = api.get("/samples")
    await expect(promise).rejects.toMatchObject({
      name: "ApiClientError",
      status,
      endpoint: "/samples",
      message: expect.stringContaining(message),
    })
    expect(notifyMock).toHaveBeenCalledWith(
      expect.objectContaining({ tone, source: "GET /samples", message: expect.stringContaining(message) }),
    )
  })

  it("preserves non-JSON response text in the user-facing error", async () => {
    vi.mocked(fetch).mockResolvedValue(response("upstream unavailable", 502, "Bad Gateway"))

    await expect(api.get("/health")).rejects.toThrow(
      "The server could not complete the request. upstream unavailable",
    )
  })

  it("redirects an expired authenticated session without creating a duplicate notification", async () => {
    vi.mocked(fetch).mockResolvedValue(response("{}", 401, "Unauthorized"))

    await expect(api.get("/samples")).rejects.toThrow("Unauthorized")
    expect(window.location.href).toBe("/login")
    expect(notifyMock).not.toHaveBeenCalled()
  })

  it("marks API errors so downstream handlers do not notify twice", () => {
    expect(new ApiClientError("failed", 400, "/records")).toMatchObject({
      notificationShown: true,
      status: 400,
      endpoint: "/records",
    })
  })
})
