import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  createNotification,
  loadNotifications,
  notify,
  saveNotifications,
  subscribeNotifications,
} from "./notification-store"

describe("notification store", () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
      },
    })
  })

  it("creates complete unread notifications with an info default", () => {
    expect(createNotification({ title: "Ready" })).toMatchObject({
      tone: "info",
      title: "Ready",
      read: false,
    })
  })

  it("loads valid arrays and fails closed for malformed storage", () => {
    storage.set("coyote3.notifications", JSON.stringify([{ id: "1" }]))
    expect(loadNotifications()).toEqual([{ id: "1" }])
    storage.set("coyote3.notifications", "not json")
    expect(loadNotifications()).toEqual([])
    storage.set("coyote3.notifications", JSON.stringify({ id: "1" }))
    expect(loadNotifications()).toEqual([])
  })

  it("retains at most 200 notifications", () => {
    saveNotifications(
      Array.from({ length: 205 }, (_, index) => createNotification({ title: `Event ${index}` })),
    )
    expect(JSON.parse(storage.get("coyote3.notifications") || "[]")).toHaveLength(200)
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
