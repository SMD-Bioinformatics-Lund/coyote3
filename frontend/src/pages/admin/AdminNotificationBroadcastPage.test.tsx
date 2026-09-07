import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { AdminNotificationBroadcastPage } from "./AdminNotificationBroadcastPage"

const mutation = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false }))
const recipients = vi.hoisted(() => ({
  users: [
    { username: "analyst.one", name: "Analyst One", email: "analyst@example.org" },
    { username: "manager.one", name: "Manager One", email: "manager@example.org" },
  ],
  roles: [{ role_id: "manager", label: "Manager", user_count: 2 }],
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: recipients, isLoading: false }),
  useMutation: () => mutation,
}))

describe("Admin notification broadcast", () => {
  beforeEach(() => {
    mutation.mutate.mockReset()
    mutation.isPending = false
  })

  async function enterMessage(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText("Title"), "Scheduled maintenance")
    await user.type(screen.getByLabelText("Message"), "The service will restart at 18:00.")
  }

  it("requires valid content and confirms an all-user broadcast", async () => {
    const user = userEvent.setup()
    renderWithRouter(<AdminNotificationBroadcastPage />)
    const send = screen.getByRole("button", { name: "Send" })
    expect(send).toBeDisabled()
    await enterMessage(user)
    expect(send).toBeEnabled()
    await user.click(send)
    expect(screen.getByText("This message will be visible to every active user.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Send notification" }))
    expect(mutation.mutate).toHaveBeenCalledOnce()
  })

  it("supports role and individual recipient selection with user search", async () => {
    const user = userEvent.setup()
    renderWithRouter(<AdminNotificationBroadcastPage />)
    await enterMessage(user)

    await user.click(screen.getByRole("button", { name: "By role" }))
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled()
    await user.click(screen.getByRole("checkbox", { name: /Manager/ }))
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled()

    await user.click(screen.getByRole("button", { name: "Individuals" }))
    await user.type(screen.getByPlaceholderText("Search users"), "analyst")
    expect(screen.getByText("Analyst One")).toBeInTheDocument()
    expect(screen.queryByText("Manager One")).not.toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: /Analyst One/ }))
    expect(screen.getByText("1 selected")).toBeInTheDocument()
  })

  it("shows empty recipient results", async () => {
    const user = userEvent.setup()
    renderWithRouter(<AdminNotificationBroadcastPage />)
    await user.click(screen.getByRole("button", { name: "Individuals" }))
    await user.type(screen.getByPlaceholderText("Search users"), "missing")
    expect(screen.getByText("No active users match this search.")).toBeInTheDocument()
  })
})
