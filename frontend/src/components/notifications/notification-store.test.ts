import { describe, expect, it, vi } from "vitest"
import { createNotification, notify, subscribeNotifications } from "./notification-store"

describe("notification store", () => {
  it("creates unread notifications without accessing browser storage", () => {
    vi.stubGlobal("window", {})
    expect(createNotification({ title: "Ready" })).toMatchObject({
      tone: "info", title: "Ready", read: false,
    })
  })

  it("delivers unique notifications, suppresses duplicates, and unsubscribes", () => {
    const listener = vi.fn()
    const unsubscribe = subscribeNotifications(listener)
    const input = { title: `Unique ${Math.random()}`, message: "one" }
    expect(notify(input)).not.toBeNull()
    expect(notify(input)).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    notify({ title: `After unsubscribe ${Math.random()}` })
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
