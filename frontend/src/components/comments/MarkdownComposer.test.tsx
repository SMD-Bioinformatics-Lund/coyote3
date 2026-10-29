import { fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { expect, it, vi } from "vitest"
import { MarkdownComposer } from "./MarkdownComposer"

it("formats selected text and previews it using the shared Markdown renderer", () => {
  function Editor() {
    const [value, setValue] = useState("Evidence")
    return <MarkdownComposer label="Note" value={value} onChange={setValue} />
  }
  render(<Editor />)
  const input = screen.getByLabelText("Note") as HTMLTextAreaElement
  input.setSelectionRange(0, 8)
  fireEvent.click(screen.getByRole("button", { name: "Bold" }))
  expect(input).toHaveValue("**Evidence**")
  fireEvent.click(screen.getByRole("button", { name: "Preview" }))
  expect(screen.getByLabelText("Note preview").querySelector("strong")).toHaveTextContent("Evidence")
})

it("renders read-only Markdown without permitting edits or unsafe HTML/links", () => {
  const change = vi.fn()
  const { container } = render(<MarkdownComposer readOnly label="Saved text"
    value={'**Evidence** <script>alert(1)</script> [bad](javascript:alert(1))'} onChange={change} />)
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  expect(screen.getByLabelText("Saved text preview").querySelector("strong")).toHaveTextContent("Evidence")
  expect(container.querySelector("script")).toBeNull()
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
  expect(screen.getByRole("button", { name: "Write" })).toBeDisabled()
  expect(change).not.toHaveBeenCalled()
})

it("keeps comment limits by default and permits unlimited rule text explicitly", () => {
  const { rerender } = render(<MarkdownComposer label="Text" value="" onChange={vi.fn()} />)
  expect(screen.getByLabelText("Text")).toHaveAttribute("maxlength", "5000")
  rerender(<MarkdownComposer label="Text" value={"a".repeat(6000)} maxLength={null} onChange={vi.fn()} />)
  expect(screen.getByLabelText("Text")).not.toHaveAttribute("maxlength")
  expect(screen.getByLabelText("Text")).toHaveValue("a".repeat(6000))
})
