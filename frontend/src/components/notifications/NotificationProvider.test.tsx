import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { NotificationProvider } from "./NotificationProvider"
import { useNotifications } from "./use-notifications"

function Probe() {
  const inbox = useNotifications()
  return (
    <div>
      <output aria-label="Unread count">{inbox.unreadCount}</output>
      {inbox.notifications.map((item) => <span key={item.id}>{item.title}</span>)}
      <button type="button" onClick={() => inbox.push({ tone: "warning", title: "Local warning", message: "Review it" })}>Push</button>
      <button type="button" onClick={() => inbox.markRead("server-1")}>Read one</button>
      <button type="button" onClick={inbox.markAllRead}>Read all</button>
      <button type="button" onClick={() => inbox.remove("server-1")}>Remove one</button>
      <button type="button" onClick={inbox.clear}>Clear</button>
    </div>
  )
}

function response(data: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(data) } as Response)
}

describe("NotificationProvider", () => {
  afterEach(() => vi.unstubAllGlobals())

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
    await user.click(screen.getByRole("button", { name: "Remove one" }))
    expect(screen.queryByText("Server notice")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Clear" }))
    expect(screen.getByLabelText("Unread count")).toHaveTextContent("0")
  })

  it("clears inbox state when the session endpoint is unauthenticated", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({}, false)))
    render(<NotificationProvider><Probe /></NotificationProvider>)
    await waitFor(() => expect(screen.getByLabelText("Unread count")).toHaveTextContent("0"))
    expect(screen.queryByText("Server notice")).not.toBeInTheDocument()
  })

  it("rejects notification context use outside its provider", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined)
    expect(() => render(<Probe />)).toThrow("useNotifications must be used inside NotificationProvider")
    error.mockRestore()
  })
})
