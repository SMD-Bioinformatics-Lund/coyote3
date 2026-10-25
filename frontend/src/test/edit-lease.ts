import { expect, type Mock } from "vitest"

/** Successful synthetic lease response for page tests exercising existing authoring flows. */
export function editLease() {
  return { owned: true, owner: "test.editor", expires_at: new Date(Date.now() + 90_000).toISOString(), renew_after_seconds: 30 }
}

export const editSessionOptions = { headers: { "X-Edit-Session": expect.any(String) } }

export function installEditLeaseMock(post: Mock) {
  const original = post.getMockImplementation()
  post.mockImplementation((url: string, ...args: unknown[]) => url.startsWith("/editing/")
    ? Promise.resolve({ status: 200, data: editLease() })
    : original?.(url, ...args))
}
