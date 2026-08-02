import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { BulkActionDropdown } from "./BulkActionDropdown"

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
    expect(onAction).toHaveBeenCalledWith("tier_2")
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })
})
