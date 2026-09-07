import { QueryClient } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { clearSessionState, SESSION_CHANGED_EVENT } from "./session-state"

describe("session boundaries", () => {
  it("clears private queries, pending results, and stored clinical text", async () => {
    const client = new QueryClient()
    client.setQueryData(["sample", "synthetic"], { private: true })
    let resolve!: (value: string) => void
    const pending = client.fetchQuery({
      queryKey: ["late"], queryFn: () => new Promise<string>(done => { resolve = done }),
    }).catch(() => undefined)
    localStorage.setItem("coyote3.notifications:synthetic", "private")
    sessionStorage.setItem("coyote3.table.synthetic.search", "private")
    localStorage.setItem("theme", "dark")
    const listener = vi.fn()
    window.addEventListener(SESSION_CHANGED_EVENT, listener)
    await clearSessionState(client)
    resolve("private")
    await pending
    expect(client.getQueryCache().getAll()).toEqual([])
    expect(localStorage.getItem("coyote3.notifications:synthetic")).toBeNull()
    expect(sessionStorage.getItem("coyote3.table.synthetic.search")).toBeNull()
    expect(localStorage.getItem("theme")).toBe("dark")
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener(SESSION_CHANGED_EVENT, listener)
  })
})
