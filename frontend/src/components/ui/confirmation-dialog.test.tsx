import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ConfirmationDialog } from "./confirmation-dialog"

describe("ConfirmationDialog", () => {
  it("does not render while closed", () => {
    render(<ConfirmationDialog open={false} title="Delete" description="Confirm" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("focuses cancel and handles confirm, cancel, escape, and backdrop", async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <ConfirmationDialog open title="Apply tier" description="This changes the classification." onConfirm={onConfirm} onCancel={onCancel} />,
    )

    expect(screen.getByRole("alertdialog")).toHaveAccessibleName("Apply tier")
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus()
    await user.click(screen.getByRole("button", { name: "Confirm" }))
    expect(onConfirm).toHaveBeenCalledOnce()
    await user.keyboard("{Escape}")
    expect(onCancel).toHaveBeenCalledOnce()
    const backdrop = screen.getByRole("alertdialog").parentElement as HTMLElement
    fireEvent.mouseDown(backdrop)
    expect(onCancel).toHaveBeenCalledTimes(2)
  })

  it("locks dismissal and reports progress while pending", async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(<ConfirmationDialog open title="Apply" description="Pending" isPending onConfirm={vi.fn()} onCancel={onCancel} />)
    expect(screen.getByRole("button", { name: "Applying" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
    await user.keyboard("{Escape}")
    expect(onCancel).not.toHaveBeenCalled()
  })
})
