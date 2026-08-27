import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { NotificationHistoryPage } from "./NotificationHistoryPage"

const notificationState = vi.hoisted(() => ({
  notifications: [] as any[],
  unreadCount: 0,
  markAllRead: vi.fn(),
  remove: vi.fn(),
  clear: vi.fn(),
}))

vi.mock("@/components/notifications/use-notifications", () => ({
  useNotifications: () => notificationState,
}))

describe("Notification history", () => {
  beforeEach(() => {
    notificationState.notifications = []
    notificationState.unreadCount = 0
    notificationState.markAllRead.mockReset()
    notificationState.remove.mockReset()
    notificationState.clear.mockReset()
  })

  it("renders an empty inbox and disables bulk actions", () => {
    renderWithRouter(<NotificationHistoryPage />)
    expect(screen.getByText("No notifications yet")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Mark read" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled()
  })

  it("renders addressed messages and dispatches inbox actions", async () => {
    notificationState.notifications = [{
      id: "notice-1",
      tone: "warning",
      category: "maintenance",
      source: "SYSTEM",
      title: "Maintenance window",
      message: "Analysis will pause briefly.",
      createdAt: "2026-08-01T10:00:00Z",
      read: false,
    }]
    notificationState.unreadCount = 1
    const user = userEvent.setup()
    renderWithRouter(<NotificationHistoryPage />)

    expect(screen.getByText("Maintenance window")).toBeInTheDocument()
    expect(screen.getByText("warning")).toBeInTheDocument()
    expect(screen.getByText("maintenance")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Mark read" }))
    await user.click(screen.getByTitle("Remove notification"))
    await user.click(screen.getByRole("button", { name: "Clear" }))
    expect(notificationState.markAllRead).toHaveBeenCalledOnce()
    expect(notificationState.remove).toHaveBeenCalledWith("notice-1")
    expect(notificationState.clear).toHaveBeenCalledOnce()
  })
})
