import { beforeEach, describe, expect, it, vi } from "vitest"
import { ApiClientError } from "./api"

const { notify } = vi.hoisted(() => ({ notify: vi.fn() }))
vi.mock("@/components/notifications/notification-store", () => ({ notify }))

describe("notification helpers", () => {
  beforeEach(() => notify.mockReset())

  it("publishes success and warning notifications with resource context", async () => {
    const { notifySuccess, notifyWarning } = await import("./notifications")
    notifySuccess("Saved", "Complete", "Reports", { type: "sample", id: "S1" })
    notifyWarning("Review", "Needs attention", "Ingest")
    expect(notify).toHaveBeenNthCalledWith(1, {
      tone: "success",
      title: "Saved",
      message: "Complete",
      source: "Reports",
      resource: { type: "sample", id: "S1" },
    })
    expect(notify).toHaveBeenNthCalledWith(2, expect.objectContaining({ tone: "warning", title: "Review" }))
  })

  it("uses useful error messages and suppresses API errors already shown", async () => {
    const { notifyActionError } = await import("./notifications")
    notifyActionError("Failed", new Error("Specific failure"), "Admin")
    notifyActionError("Failed", "String failure")
    notifyActionError("Failed", {})
    expect(notify).toHaveBeenNthCalledWith(1, expect.objectContaining({ message: "Specific failure" }))
    expect(notify).toHaveBeenNthCalledWith(2, expect.objectContaining({ message: "String failure" }))
    expect(notify).toHaveBeenNthCalledWith(3, expect.objectContaining({ message: "The action could not be completed." }))

    const alreadyShown = new ApiClientError("Already shown", 500)
    notifyActionError("Failed", alreadyShown)
    expect(notify).toHaveBeenCalledTimes(3)
  })
})
