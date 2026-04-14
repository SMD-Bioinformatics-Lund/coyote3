import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { loadScript } from "./helpers/loadScript.mjs";

describe("api_client.js (window.coyoteApi)", () => {
  let fetchMock;

  beforeAll(() => {
    loadScript("api_client.js");
  });

  beforeEach(() => {
    delete window.COYOTE_API_BASE;
    fetchMock = vi.fn();
    window.fetch = fetchMock;
  });

  afterEach(() => {
    delete window.fetch;
    delete window.COYOTE_API_BASE;
  });

  function mockJsonResponse(body, { status = 200 } = {}) {
    fetchMock.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => "application/json" },
      json: async () => body,
      text: async () => JSON.stringify(body),
    });
  }

  function mockTextResponse(body, { status = 200 } = {}) {
    fetchMock.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => "text/plain" },
      json: async () => {
        throw new Error("not json");
      },
      text: async () => body,
    });
  }

  it("exposes get/post/request on window.coyoteApi", () => {
    expect(typeof window.coyoteApi).toBe("object");
    expect(typeof window.coyoteApi.get).toBe("function");
    expect(typeof window.coyoteApi.post).toBe("function");
    expect(typeof window.coyoteApi.request).toBe("function");
  });

  it("defaults the API base to /api and prepends /v1 to the path", async () => {
    mockJsonResponse({ ok: true });
    await window.coyoteApi.get("/samples");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/samples");
  });

  it("respects window.COYOTE_API_BASE override and strips trailing slashes", async () => {
    window.COYOTE_API_BASE = "https://example.com/coyote/api/";
    mockJsonResponse({ ok: true });
    await window.coyoteApi.get("samples"); // also tests missing leading slash
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("https://example.com/coyote/api/v1/samples");
  });

  it("encodes query params and skips null/undefined/empty values", async () => {
    mockJsonResponse({ ok: true });
    await window.coyoteApi.get("/samples", {
      q: "TP53 mutation",
      page: 2,
      empty: "",
      missing: null,
      undef: undefined,
    });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("q=TP53%20mutation");
    expect(url).toContain("page=2");
    expect(url).not.toContain("empty=");
    expect(url).not.toContain("missing=");
    expect(url).not.toContain("undef=");
  });

  it("sends X-Requested-With header on every request", async () => {
    mockJsonResponse({ ok: true });
    await window.coyoteApi.get("/samples");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Requested-With"]).toBe("XMLHttpRequest");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("same-origin");
  });

  it("serializes plain object bodies as JSON with content-type", async () => {
    mockJsonResponse({ id: 1 });
    await window.coyoteApi.post("/samples", { name: "x", count: 3 });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ name: "x", count: 3 }));
  });

  it("does NOT JSON-encode FormData bodies", async () => {
    mockJsonResponse({ ok: true });
    const fd = new FormData();
    fd.append("file", "x");
    await window.coyoteApi.request("/upload", { method: "POST", body: fd });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(fd);
    expect(init.headers["Content-Type"]).toBeUndefined();
  });

  it("returns parsed JSON for application/json responses", async () => {
    mockJsonResponse({ hello: "world" });
    const result = await window.coyoteApi.get("/foo");
    expect(result).toEqual({ hello: "world" });
  });

  it("returns text for non-JSON responses", async () => {
    mockTextResponse("plain body");
    const result = await window.coyoteApi.get("/foo");
    expect(result).toBe("plain body");
  });

  it("throws an Error with status and payload on non-2xx responses", async () => {
    mockJsonResponse({ error: "boom" }, { status: 500 });
    await expect(window.coyoteApi.get("/foo")).rejects.toMatchObject({
      message: "boom",
      status: 500,
      payload: { error: "boom" },
    });
  });

  it("falls back to a generic error message when payload has no error field", async () => {
    mockJsonResponse({}, { status: 404 });
    await expect(window.coyoteApi.get("/foo")).rejects.toMatchObject({
      message: "API request failed (404)",
      status: 404,
    });
  });
});
