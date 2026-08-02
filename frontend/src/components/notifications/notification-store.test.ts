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
    storage.set("coyote3.notifications:user.one", JSON.stringify([{ id: "1" }]))
    expect(loadNotifications("user.one")).toEqual([{ id: "1" }])
    expect(loadNotifications("user.two")).toEqual([])
    storage.set("coyote3.notifications:user.one", "not json")
    expect(loadNotifications("user.one")).toEqual([])
    storage.set("coyote3.notifications:user.one", JSON.stringify({ id: "1" }))
    expect(loadNotifications("user.one")).toEqual([])
  })

  it("retains at most 200 notifications", () => {
    saveNotifications(
      "user.one",
      Array.from({ length: 205 }, (_, index) => createNotification({ title: `Event ${index}` })),
    )
    expect(JSON.parse(storage.get("coyote3.notifications:user.one") || "[]")).toHaveLength(200)
  })

  it("does not copy durable server messages into browser storage", () => {
    saveNotifications("user.one", [
      { ...createNotification({ title: "Local" }), persisted: false },
      { ...createNotification({ title: "Server" }), persisted: true },
    ])

    expect(JSON.parse(storage.get("coyote3.notifications:user.one") || "[]")).toHaveLength(1)
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
