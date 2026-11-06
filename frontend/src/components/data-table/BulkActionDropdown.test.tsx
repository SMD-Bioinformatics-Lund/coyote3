import { act, render as renderUI, screen, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren, ReactElement } from "react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { BulkActionDropdown } from "./BulkActionDropdown"

function render(element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return renderUI(element, { wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider> })
}

describe("BulkActionDropdown", () => {
  it("keeps failed actions open for retry and blocks duplicate submissions", async () => {
    const user = userEvent.setup()
    let complete!: () => void
    const pending = new Promise<void>(resolve => { complete = resolve })
    const onAction = vi.fn().mockRejectedValueOnce(new Error("Action failed"))
      .mockReturnValueOnce(pending)
    render(<BulkActionDropdown selectedIds={["one"]} onAction={onAction} />)
    await user.selectOptions(screen.getByRole("combobox"), "tier_1")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("button", { name: "Apply action" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Action failed")
    await user.click(screen.getByRole("button", { name: "Apply action" }))
    expect(screen.getByRole("combobox")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
    const confirm = within(screen.getByRole("alertdialog")).getByRole("button", { name: "Applying" })
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    expect(onAction).toHaveBeenCalledTimes(2)
    await act(async () => { complete(); await pending })
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("requires a fresh annotation preview after a failed write", async () => {
    const user = userEvent.setup()
    const onAction = vi.fn().mockRejectedValue(new Error("Rule version changed"))
    const onPreview = vi.fn().mockResolvedValue([
      { resource_id: "one", content_hash: "hash", gene: null, rule_id: null, text: null },
    ])
    render(<BulkActionDropdown selectedIds={["one"]} onAction={onAction}
      automaticTextAvailable onPreviewAutomaticText={onPreview} />)
    await user.selectOptions(screen.getByRole("combobox"), "tier_1")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    await user.click(screen.getByRole("button", { name: "Apply action" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Rule version changed")
    expect(screen.getByRole("button", { name: "Apply action" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    expect(onPreview).toHaveBeenCalledTimes(2)
    expect(screen.getByRole("button", { name: "Apply action" })).toBeEnabled()
  })

  it("discards a pending preview when the selected findings change without changing count", async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    let complete!: (rows: { resource_id: string; content_hash: string; gene: null; rule_id: null; text: null }[]) => void
    const pending = new Promise<{ resource_id: string; content_hash: string; gene: null; rule_id: null; text: null }[]>(resolve => { complete = resolve })
    const props = { onAction, automaticTextAvailable: true, onPreviewAutomaticText: () => pending }
    const view = render(<BulkActionDropdown {...props} selectedIds={["one"]} />)
    await user.selectOptions(screen.getByRole("combobox"), "tier_1")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    view.rerender(<BulkActionDropdown {...props} selectedIds={["two"]} />)
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    await act(async () => { complete([{ resource_id: "one", content_hash: "hash", gene: null, rule_id: null, text: null }]); await pending })
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    expect(screen.getByRole("button", { name: "Apply action" })).toBeDisabled()
    expect(onAction).not.toHaveBeenCalled()
  })

  it.each([
    [["one", "hash"], ["one", "hash"]],
    [["one", "hash"], ["other", "hash"]],
    [["one", "hash"], ["two", "different-hash"]],
    [["one", ""], ["two", ""]],
  ])("rejects previews that do not identify the exact selection and one release: %j", async (...rows) => {
    const user = userEvent.setup()
    render(<BulkActionDropdown selectedIds={["one", "two"]} onAction={vi.fn()} automaticTextAvailable
      onPreviewAutomaticText={async () => rows.map(([resource_id, content_hash]) => ({ resource_id, content_hash, gene: null, rule_id: null, text: null }))} />)
    await user.selectOptions(screen.getByRole("combobox"), "tier_1")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    await screen.findByText(/preview does not match the selected findings/)
    expect(screen.getByRole("button", { name: "Apply action" })).toBeDisabled()
  })

  it("disables an action removed by a capability update", async () => {
    const onAction = vi.fn()
    const view = render(<BulkActionDropdown selectedIds={["one"]} onAction={onAction} />)
    await userEvent.selectOptions(screen.getByRole("combobox"), "tier_1")
    view.rerender(<BulkActionDropdown selectedIds={["one"]} onAction={onAction} actions={[{ value: "fp", label: "Mark False Positive" }]} />)
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled()
    expect(onAction).not.toHaveBeenCalled()
  })
  it("is absent without a selection", () => {
    render(<BulkActionDropdown selectedIds={[]} onAction={vi.fn()} />)
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument()
  })

  it("requires an action and confirms before applying it", async () => {
    const user = userEvent.setup()
    const onAction = vi.fn().mockResolvedValue(undefined)
    render(
      <BulkActionDropdown
        selectedIds={["one", "two", "three"]}
        onAction={onAction}
        actions={[{ value: "tier_2", label: "Classify as Tier 2" }]}
      />,
    )
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled()
    await user.selectOptions(screen.getByRole("combobox"), "tier_2")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    expect(screen.getByRole("alertdialog")).toHaveTextContent("3 selected finding(s)")
    await user.click(screen.getByRole("button", { name: "Apply action" }))
    expect(onAction).toHaveBeenCalledWith("tier_2", { includeAutomaticText: false })
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("keeps confirmation disabled when annotation preview fails", async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    render(<BulkActionDropdown selectedIds={["one"]} onAction={onAction} automaticTextAvailable
      onPreviewAutomaticText={async () => { throw new Error("Rules unavailable") }} />)
    await user.selectOptions(screen.getByRole("combobox"), "tier_1")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Rules unavailable")
    expect(screen.getByRole("button", { name: "Apply action" })).toBeDisabled()
    expect(onAction).not.toHaveBeenCalled()
  })

  it.each([1, 2, 3])("previews optional annotation text for bulk Tier %i", async tier => {
    const user = userEvent.setup()
    const onAction = vi.fn().mockResolvedValue(undefined)
    render(
      <BulkActionDropdown
        selectedIds={["one", "two"]}
        onAction={onAction}
        automaticTextAvailable
        onPreviewAutomaticText={async () => [
          { resource_id: "one", content_hash: "reviewed-hash", gene: "GENE_A", rule_id: "rule", text: "**Reviewed** annotation" },
          { resource_id: "two", content_hash: "reviewed-hash", gene: "GENE_B", rule_id: null, text: null },
        ]}
        actions={[
          { value: "tier_1", label: "Classify as Tier 1" },
          { value: "tier_2", label: "Classify as Tier 2" },
          { value: "tier_3", label: "Classify as Tier 3" },
        ]}
      />,
    )

    await user.selectOptions(screen.getByRole("combobox"), `tier_${tier}`)
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("checkbox", { name: "Include automatic text" }))
    expect(screen.getByRole("button", { name: "Apply action" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Preview annotation text" }))
    expect(await screen.findByText(/1 with annotation text; 1 without/)).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Apply action" }))

    expect(onAction).toHaveBeenCalledWith(`tier_${tier}`, { includeAutomaticText: true, annotationRuleHash: "reviewed-hash" })
  })
})
