import { afterEach, describe, expect, it, vi } from "vitest"

import { downloadBlob, downloadText } from "@/lib/browser-download"

describe("browser downloads", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it("downloads text with a temporary object URL", () => {
    vi.useFakeTimers()
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test")
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)

    downloadText("a,b\n1,2", "rows.csv", "text/csv;charset=utf-8")

    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(click).toHaveBeenCalledOnce()
    expect(document.querySelector("a[download='rows.csv']")).toBeNull()
    expect(revokeObjectURL).not.toHaveBeenCalled()

    vi.runAllTimers()
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test")
  })

  it("removes the anchor and schedules URL cleanup when the click fails", () => {
    vi.useFakeTimers()
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:failed")
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("blocked")
    })

    expect(() => downloadBlob(new Blob(["payload"]), "payload.txt")).toThrow("blocked")
    expect(document.querySelector("a")).toBeNull()

    vi.runAllTimers()
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:failed")
  })
})
