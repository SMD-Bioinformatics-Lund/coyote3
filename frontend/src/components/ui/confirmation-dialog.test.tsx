import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"

import { ConfirmationDialog } from "./confirmation-dialog"

describe("ConfirmationDialog", () => {
  it("keeps focus while typing into controlled fields and traps keyboard navigation", async () => {
    function Example() {
      const [open, setOpen] = useState(false)
      const [reason, setReason] = useState("")
      return <><button onClick={() => setOpen(true)}>Open</button><ConfirmationDialog open={open} title="Change status" description={<label>Reason<textarea value={reason} onChange={event => setReason(event.target.value)} /></label>} onCancel={() => setOpen(false)} onConfirm={() => setOpen(false)} /></>
    }
    const user = userEvent.setup()
    render(<Example />)
    await user.click(screen.getByRole("button", { name: "Open" }))
    await user.click(screen.getByLabelText("Reason"))
    await user.type(screen.getByLabelText("Reason"), "Pause new work")
    expect(screen.getByLabelText("Reason")).toHaveValue("Pause new work")
    expect(screen.getByLabelText("Reason")).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByRole("button", { name: "Confirm" })).toHaveFocus()
    await user.tab()
    expect(screen.getByLabelText("Reason")).toHaveFocus()
    await user.keyboard("{Escape}")
    expect(screen.getByRole("button", { name: "Open" })).toHaveFocus()
    expect(document.body.style.overflow).not.toBe("hidden")
  })

  it("allows dismissal while confirmation is unavailable", async () => {
    const cancel = vi.fn()
    render(<ConfirmationDialog open title="Unavailable" description="Loading impact" confirmDisabled onCancel={cancel} onConfirm={vi.fn()} />)
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled()
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }))
    expect(cancel).toHaveBeenCalledOnce()
  })
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
