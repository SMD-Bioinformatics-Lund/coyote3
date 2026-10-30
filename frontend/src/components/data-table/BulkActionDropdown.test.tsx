import { render as renderUI, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactElement } from "react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { BulkActionDropdown } from "./BulkActionDropdown"

function render(element: ReactElement) {
  return renderUI(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>{element}</QueryClientProvider>)
}

describe("BulkActionDropdown", () => {
  it("is absent without a selection", () => {
    render(<BulkActionDropdown selectedCount={0} onAction={vi.fn()} />)
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument()
  })

  it("requires an action and confirms before applying it", async () => {
    const user = userEvent.setup()
    const onAction = vi.fn().mockResolvedValue(undefined)
    render(
      <BulkActionDropdown
        selectedCount={3}
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
    render(<BulkActionDropdown selectedCount={1} onAction={onAction} automaticTextAvailable
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
        selectedCount={2}
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
