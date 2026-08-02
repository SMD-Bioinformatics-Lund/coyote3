import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { useSingleFindingFlag } from "@/hooks/useFindingActions"
import { VariantActionButtons } from "./VariantActionButtons"

const mutateAsync = vi.fn()
vi.mock("@/hooks/useFindingActions", () => ({ useSingleFindingFlag: vi.fn(() => ({ mutateAsync, isPending: false })) }))
vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn(), notifySuccess: vi.fn() }))

function renderActions(props: React.ComponentProps<typeof VariantActionButtons>) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <VariantActionButtons {...props} />
    </QueryClientProvider>,
  )
}

describe("VariantActionButtons", () => {
  beforeEach(() => {
    mutateAsync.mockReset().mockResolvedValue(undefined)
    vi.mocked(api.post).mockReset().mockResolvedValue({ data: {} } as never)
    vi.mocked(useSingleFindingFlag).mockClear()
  })

  it("confirms and applies a false-positive state transition", async () => {
    const user = userEvent.setup()
    const onUpdate = vi.fn()
    renderActions({ sampleId: "CASE_1", variant: { _id: "v1" }, onUpdate })

    await user.click(screen.getByTitle("Toggle False Positive"))
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Mark finding as false positive?")
    await user.click(screen.getByRole("button", { name: "Mark false positive" }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ resourceId: "v1", flag: "false-positive", apply: true }))
    expect(onUpdate).toHaveBeenCalledOnce()
  })

  it("shows only actions supported by a fusion finding", () => {
    renderActions({ sampleId: "CASE_1", resourceType: "fusion", variant: { _id: "f1" }, compact: true, showReportLabel: true })
    expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument()
    expect(screen.queryByTitle("Toggle False Positive")).toBeInTheDocument()
    expect(screen.queryByTitle("Toggle Irrelevant")).not.toBeInTheDocument()
    expect(screen.queryByTitle("Add to blacklist")).not.toBeInTheDocument()
  })

  it("adds an eligible small variant to the center blacklist after confirmation", async () => {
    const user = userEvent.setup()
    renderActions({ sampleId: "CASE_1", variant: { _id: "v1" } })
    await user.click(screen.getByTitle("Add to blacklist"))
    await user.click(screen.getByRole("button", { name: "Add to blacklist" }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/samples/CASE_1/small-variants/v1/blacklist-entries", {}))
  })
})
