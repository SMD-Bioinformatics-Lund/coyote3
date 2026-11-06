import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { NotificationProvider } from "./NotificationProvider"
import { useNotifications } from "./use-notifications"

function Probe({ title = "Local warning" }: { title?: string }) {
  const inbox = useNotifications()
  return (
    <div>
      <output aria-label="Unread count">{inbox.unreadCount}</output>
      <output aria-label="Server read state">{String(inbox.notifications.find(item => item.id === "server-1")?.read)}</output>
      {inbox.notifications.map((item) => <span key={item.id}>{item.title}</span>)}
      <button type="button" onClick={() => inbox.push({ tone: "warning", title, message: "Review it" })}>Push</button>
      <button type="button" onClick={() => inbox.markRead("server-1")}>Read one</button>
      <button type="button" onClick={() => inbox.markUnread("server-1")}>Unread one</button>
      <button type="button" onClick={inbox.markAllRead}>Read all</button>
      <button type="button" onClick={() => inbox.remove("server-1")}>Remove one</button>
      <button type="button" onClick={inbox.clear}>Clear</button>
    </div>
  )
}

function response(data: unknown, ok = true) {
  return Promise.resolve({ ok, text: () => Promise.resolve(JSON.stringify(data)), json: () => Promise.resolve(data) } as Response)
}

describe("NotificationProvider", () => {
  afterEach(() => { vi.unstubAllGlobals(); window.sessionStorage.clear() })

  it("does not overwrite a newer inbox refresh with an older response", async () => {
    let finish!: (value: Response) => void
    let inboxCalls = 0
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("whoami")) return response({ username: "reader" })
      if (++inboxCalls === 1) return new Promise<Response>(resolve => { finish = resolve })
      return response({ notifications: [{ id: "server-1", title: "Current notice", tone: "info",
        created_at: "2026-10-25T12:00:00Z", read: false }] })
    }))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await waitFor(() => expect(inboxCalls).toBe(1))
    window.dispatchEvent(new Event("focus"))
    await screen.findByText("Current notice")
    await act(async () => finish(await response({ notifications: [] })))
    expect(screen.getByText("Current notice")).toBeInTheDocument()
  })

  it("ignores a malformed saved local inbox", async () => {
    window.sessionStorage.setItem("coyote3:notification-tray:reader", '{"local":{}}')
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => response(
      String(input).includes("whoami") ? { username: "reader" } : { notifications: [] },
    )))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("0")
  })

  it.each(["Read one", "Read all"])("does not mark notifications read when %s fails", async (action) => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes("whoami")) return response({ username: "reader" })
      if (init?.method === "PATCH") return response({}, false)
      return response({ notifications: [{ id: "server-1", title: "Unread notice", tone: "info",
        created_at: "2026-10-25T12:00:00Z", read: false }] })
    }))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await screen.findByText("Unread notice")
    await userEvent.click(screen.getByRole("button", { name: action }))
    expect(screen.getByLabelText("Server read state")).toHaveTextContent("false")
  })

  it("retains the inbox during a temporary identity service failure", async () => {
    let unavailable = false
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("whoami")) return unavailable
        ? Promise.resolve(new Response("", { status: 503 })) : response({ username: "reader" })
      return response({ notifications: [{ id: "server-1", title: "Retained notice", tone: "info",
        created_at: "2026-10-25T12:00:00Z", read: false }] })
    }))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await screen.findByText("Retained notice")
    unavailable = true
    window.dispatchEvent(new Event("focus"))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3))
    expect(screen.getByText("Retained notice")).toBeInTheDocument()
  })

  it("merges the current user's server inbox with local notifications and persists server actions", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.includes("/auth/whoami")) return response({ username: "Clinician" })
      if (path.includes("/notifications?limit=200")) {
        return response({
          notifications: [{
            id: "server-1",
            tone: "info",
            category: "application",
            title: "Server notice",
            message: "A persisted message",
            source: "Operations",
            resource: { type: "sample", id: "S1", sample_name: "CASE-1", finding: "TP53" },
            created_at: "2026-08-02T12:00:00Z",
            read: false,
          }],
        })
      }
      return response({ method: init?.method })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<NotificationProvider><Probe /></NotificationProvider>)

    expect(await screen.findByText("Server notice")).toBeInTheDocument()
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("1")

    await user.click(screen.getByRole("button", { name: "Push" }))
    expect(await screen.findAllByText("Local warning")).toHaveLength(2)
    expect(screen.getByText("Review it")).toBeInTheDocument()
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("2")

    await user.click(screen.getByRole("button", { name: "Read one" }))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("1")
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/notifications/server-1/read"),
      expect.objectContaining({ method: "PATCH" }),
    ))

    await user.click(screen.getByRole("button", { name: "Read all" }))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("0")
    expect(screen.getByText("Server notice")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Unread one" }))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("1")
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/notifications/server-1/unread"),
      expect.objectContaining({ method: "PATCH" }),
    ))
    await user.click(screen.getByRole("button", { name: "Remove one" }))
    await waitFor(() => expect(screen.queryByText("Server notice")).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/notifications/server-1/dismiss"),
      expect.objectContaining({ method: "PATCH" }),
    )
    await user.click(screen.getByRole("button", { name: "Clear" }))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("0")
    window.dispatchEvent(new Event("focus"))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("whoami"))).toHaveLength(2))
    expect(screen.queryByText("Server notice")).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false)
  })

  it("clears inbox state when the session endpoint is unauthenticated", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({}, false)))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await waitFor(() => expect(screen.getByLabelText("Unread count")).toHaveTextContent("0"))
    expect(screen.queryByText("Server notice")).not.toBeInTheDocument()
  })

  it("keeps a notification visible when its dismissal cannot be saved", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("whoami")) return response({ username: "reader" })
      if (path.endsWith("/dismiss")) return response({ detail: "Unavailable" }, false)
      return response({ notifications: [{
        id: "server-1", title: "Unsaved notice", message: "Synthetic",
        created_at: "2026-10-25T12:00:00Z", read: false,
      }] })
    }))
    const user = userEvent.setup()
    render(<NotificationProvider><Probe /></NotificationProvider>)
    expect(await screen.findByText("Unsaved notice")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Remove one" }))
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/notifications/server-1/dismiss"),
      expect.objectContaining({ method: "PATCH" }),
    ))
    expect(screen.getByText("Unsaved notice")).toBeVisible()
  })

  it.each(["Remove one", "Clear"])("persists %s across a new browser session", async (action) => {
    let dismissed = false
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.includes("whoami")) return response({ username: "reader" })
      if (path.endsWith("/dismiss") || init?.method === "DELETE") {
        dismissed = true
        return response({ status: "ok", changed: 1 })
      }
      return response({ notifications: dismissed ? [] : [{
        id: "server-1", title: "Persisted notice", message: "Synthetic",
        created_at: "2026-10-25T12:00:00Z", read: true, is_broadcast: true,
      }] })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const first = render(<NotificationProvider><Probe /></NotificationProvider>)
    expect(await screen.findByText("Persisted notice")).toBeVisible()
    await user.click(screen.getByRole("button", { name: action }))
    await waitFor(() => expect(screen.queryByText("Persisted notice")).not.toBeInTheDocument())
    expect(dismissed).toBe(true)
    first.unmount()
    window.sessionStorage.clear()
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("whoami"))).toHaveLength(2))
    expect(screen.queryByText("Persisted notice")).not.toBeInTheDocument()
  })

  it("retains a toast as a read inbox item when closed", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => response(
      String(input).includes("whoami") ? { username: "reader" } : { notifications: [] }
    )))
    const user = userEvent.setup()
    render(<NotificationProvider><Probe title="Retained warning" /></NotificationProvider>)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    await user.click(screen.getByRole("button", { name: "Push" }))
    await user.click(screen.getByRole("button", { name: "Dismiss notification" }))
    expect(screen.getAllByText("Retained warning")).toHaveLength(1)
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("0")
    await user.click(screen.getByRole("button", { name: "Clear" }))
    expect(screen.queryByText("Retained warning")).not.toBeInTheDocument()
  })

  it("rejects notification context use outside its provider", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined)
    expect(() => render(<Probe />)).toThrow("useNotifications must be used inside NotificationProvider")
    error.mockRestore()
  })
})
