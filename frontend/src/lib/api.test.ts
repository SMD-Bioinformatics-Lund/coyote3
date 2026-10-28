import { beforeEach, describe, expect, it, vi } from "vitest"

const notifyMock = vi.hoisted(() => vi.fn())

vi.mock("@/components/notifications/notification-store", () => ({ notify: notifyMock }))

import {
  ApiClientError,
  api,
  reportUiError,
  setCsrfToken,
} from "./api"

function response(body: string, status = 200, statusText = "OK") {
  return new Response(body, { status, statusText, headers: { "Content-Type": "application/json" } })
}

describe("typed API client", () => {
  it("loads binary reports and keeps structured errors with reference IDs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("%PDF-1.7\n%%EOF", { headers: { "Content-Type": "application/pdf" } }))
    const result = await api.getBlob("/reports/preview/pdf")
    expect(await result.data.text()).toBe("%PDF-1.7\n%%EOF")
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{"message":"Preview unavailable"}', {
      status: 422, headers: { "X-Request-ID": "synthetic-reference" },
    }))
    await expect(api.getBlob("/reports/preview/pdf", { errorNotice: "inline" })).rejects.toMatchObject({
      status: 422, requestId: "synthetic-reference", handledInline: true,
    })
  })
  beforeEach(() => {
    notifyMock.mockReset()
    vi.stubGlobal("window", { location: { pathname: "/samples", href: "/samples" } })
    vi.stubGlobal("fetch", vi.fn())
    setCsrfToken(null)
  })

  it("allows an inline preview to handle HTTP errors without posting a global notification", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(JSON.stringify({ detail: "Draft is incomplete" }), 422, "Unprocessable Entity"))
    await expect(api.post("/preview", {}, { errorNotice: "inline" })).rejects.toMatchObject({ status: 422, notificationShown: false, handledInline: true })
    expect(notifyMock).not.toHaveBeenCalled()
    expect(vi.mocked(fetch).mock.calls[0][1]).not.toHaveProperty("errorNotice")
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

  it("sends an OpenAPI-checked operation with encoded path/query values and existing CSRF handling", async () => {
    vi.mocked(fetch).mockResolvedValue(response('{"report":{"id":"synthetic"}}'))
    setCsrfToken("synthetic-csrf")
    await api.contract("POST /samples/{sample_id}/reports/{report_type}", {
      path: { sample_id: "synthetic/case", report_type: "dna" },
      body: { preview_fingerprint: "a".repeat(64) },
    })
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe("/api/v1/samples/synthetic%2Fcase/reports/dna")
    expect(options?.method).toBe("POST")
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("synthetic-csrf")
    expect(JSON.parse(String(options?.body))).toEqual({ preview_fingerprint: "a".repeat(64) })
  })

  it("serializes typed sample filters and keeps cancellation attached to the request", async () => {
    vi.mocked(fetch).mockResolvedValue(response('{"live_samples":[],"done_samples":[]}'))
    const controller = new AbortController()
    await api.contract("GET /samples", {
      query: { panel_type: "dna", assay_group: "synthetic group", live_page: 1 },
      signal: controller.signal,
    })
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/v1/samples?panel_type=dna&assay_group=synthetic+group&live_page=1")
    expect(vi.mocked(fetch).mock.calls[0][1]?.signal).toBe(controller.signal)
  })

  it("shows HTTP detail strings and structured field validation reasons", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(JSON.stringify({ detail: "CNV file 'synthetic.json' is empty" }), 400, "Bad Request"))
    await expect(api.post("/internal/ingest/sample-bundle/upload/async", {})).rejects.toThrow("CNV file 'synthetic.json' is empty")
    vi.mocked(fetch).mockResolvedValueOnce(response(JSON.stringify({ detail: [{ loc: ["body", "asp_id"], msg: "Field required", input: "private-input" }] }), 422, "Unprocessable Entity"))
    await expect(api.post("/admin/asp", {})).rejects.toThrow("body.asp_id: Field required")
    expect(JSON.stringify(notifyMock.mock.calls)).not.toContain("private-input")
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

  it("captures CSRF from an optional public-page identity check before saving UI settings", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response('{"username":"synthetic","csrf_token":"public-session-csrf"}'))
      .mockResolvedValueOnce(response("{}"))
    await api.get("/auth/whoami", { redirectOnUnauthorized: false, errorNotice: "inline" })
    await api.patch("/users/me/ui-settings", { theme: "dark" })
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get("X-CSRF-Token"))
      .toBe("public-session-csrf")
    expect(vi.mocked(fetch).mock.calls[0][1]).not.toHaveProperty("redirectOnUnauthorized")
  })

  it("leaves an anonymous public page in place and clears stale CSRF state", async () => {
    setCsrfToken("stale-session-csrf")
    vi.mocked(fetch)
      .mockResolvedValueOnce(response("{}", 401, "Unauthorized"))
      .mockResolvedValueOnce(response("{}"))
    await expect(api.get("/auth/whoami", { redirectOnUnauthorized: false, errorNotice: "inline" }))
      .rejects.toMatchObject({ status: 401, notificationShown: false })
    expect(window.location.href).toBe("/samples")
    expect(notifyMock).not.toHaveBeenCalled()
    await api.patch("/users/me/ui-settings", { theme: "light" })
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).has("X-CSRF-Token")).toBe(false)
  })

  it.each([
    [403, '{"error":"Review must be performed by another user"}', "Review must be performed by another user", "warning"],
    [404, '{"error":"Sample not found"}', "Sample not found", "warning"],
    [409, '{"message":"Already exists"}', "Already exists", "warning"],
    [422, '{"error":"Invalid payload","details":"name is required"}', "Invalid payload: name is required", "warning"],
    [500, '{"error":"Internal error","details":"database unavailable"}', "The server could not complete the request.", "error"],
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

  it("does not expose non-JSON proxy responses in the user-facing error", async () => {
    vi.mocked(fetch).mockResolvedValue(response("upstream unavailable", 502, "Bad Gateway"))

    await expect(api.get("/health")).rejects.toThrow(
      "A dependent service failed.",
    )
  })

  it("explains proxy upload limits without displaying an HTML error page", async () => {
    vi.mocked(fetch).mockResolvedValue(response("<html>nginx internal address</html>", 413))
    await expect(api.post("/upload", {})).rejects.toThrow("The upload is too large.")
    expect(JSON.stringify(notifyMock.mock.calls)).not.toContain("nginx")
  })

  it("preserves validation fields, hints, reference IDs and retry headers", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({
      error: "Validation failed", code: "validation_failed", hint: "Choose an associated diagnosis.",
      details: [{ field: "diagnosis_id", message: "Not associated with this assay" }],
    }), { status: 422, headers: { "X-Request-ID": "reference-42", "Retry-After": "30" } }))
    await expect(api.post("/admin/aspc", {})).rejects.toMatchObject({
      requestId: "reference-42", code: "validation_failed", retryAfter: "30",
      message: expect.stringContaining("diagnosis_id: Not associated with this assay"),
    })
    expect(notifyMock.mock.calls[0][0].message).toContain("Choose an associated diagnosis.")
    expect(notifyMock.mock.calls[0][0].message).toContain("Reference: reference-42")
  })

  it("normalizes network failures without notifying cancelled requests", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"))
    await expect(api.get("/records")).rejects.toMatchObject({ status: 0, code: "network_error" })
    notifyMock.mockReset()
    const abort = new DOMException("Cancelled", "AbortError")
    vi.mocked(fetch).mockRejectedValueOnce(abort)
    await expect(api.get("/records")).rejects.toBe(abort)
    expect(notifyMock).not.toHaveBeenCalled()
  })

  it("redirects an expired authenticated session without creating a duplicate notification", async () => {
    vi.mocked(fetch).mockResolvedValue(response("{}", 401, "Unauthorized"))

    await expect(api.get("/samples")).rejects.toMatchObject({
      message: "Unauthorized", status: 401, notificationShown: true,
    })
    expect(window.location.href).toBe("/login")
    expect(notifyMock).not.toHaveBeenCalled()
  })

  it.each(["/samples", "/change-password"])(
    "uses the required password-change page without notifying or reloading it from %s",
    async (pathname) => {
      const redirect = vi.fn()
      vi.stubGlobal("window", { location: { pathname, set href(value: string) { redirect(value) } } })
      vi.mocked(fetch).mockResolvedValue(response(
        JSON.stringify({ category: "password_change_required" }), 403, "Forbidden",
      ))
      await expect(api.get("/samples")).rejects.toMatchObject({ status: 403 })
      if (pathname === "/change-password") expect(redirect).not.toHaveBeenCalled()
      else expect(redirect).toHaveBeenCalledWith("/change-password")
      expect(notifyMock).not.toHaveBeenCalled()
    },
  )

  it("marks API errors so downstream handlers do not notify twice", () => {
    expect(new ApiClientError("failed", 400, "/records")).toMatchObject({
      notificationShown: true,
      status: 400,
      endpoint: "/records",
    })
  })

  it("reports bounded authenticated UI errors without recursive notifications", async () => {
    reportUiError(new Error("not signed in"))
    expect(fetch).not.toHaveBeenCalled()
    setCsrfToken("synthetic-csrf")
    vi.mocked(fetch).mockRejectedValue(new Error("API unavailable"))
    reportUiError(new Error("x".repeat(5000)), "component stack")
    await Promise.resolve()
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe("/api/v1/client-errors")
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("synthetic-csrf")
    const body = JSON.parse(String(options?.body))
    expect(body.message).toHaveLength(4000)
    expect(body.stack).toContain("component stack")
    expect(notifyMock).not.toHaveBeenCalled()
    for (let index = 0; index < 20; index += 1) reportUiError("repeated failure")
    await Promise.resolve()
    expect(fetch).toHaveBeenCalledTimes(10)
  })
})
