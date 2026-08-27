import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { notifySuccess } from "@/lib/notifications"
import { ServerCsvButton } from "./ServerCsvButton"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn(), notifySuccess: vi.fn() }))
vi.mock("@tanstack/react-query", () => ({
  useMutation: (options: any) => ({
    isPending: false,
    error: null,
    mutate: async () => {
      try {
        const result = await options.mutationFn()
        options.onSuccess?.(result)
      } catch (error) {
        options.onError?.(error)
      }
    },
  }),
}))

function renderButton() {
  return render(<ServerCsvButton endpoint="/samples/CASE_1/export" fallbackFilename="fallback.csv" />)
}

describe("ServerCsvButton", () => {
  beforeEach(() => vi.mocked(api.get).mockReset())

  it("downloads backend CSV content and reports success", async () => {
    const user = userEvent.setup()
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    vi.mocked(api.get).mockResolvedValue({ data: { content: "gene,tier\nTP53,1", filename: "findings.csv" } } as never)
    renderButton()

    await user.click(screen.getByRole("button", { name: "Export to CSV" }))

    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/samples/CASE_1/export"))
    expect(click).toHaveBeenCalledOnce()
    expect(notifySuccess).toHaveBeenCalledWith("CSV exported", "findings.csv was downloaded.", "Export")
  })

  it("uses the configured fallback filename when the server omits one", async () => {
    const user = userEvent.setup()
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    vi.mocked(api.get).mockResolvedValue({ data: { content: "gene\nTP53" } } as never)
    renderButton()

    await user.click(screen.getByRole("button", { name: "Export to CSV" }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(notifySuccess).toHaveBeenCalledWith("CSV exported", "fallback.csv was downloaded.", "Export")
  })
})
