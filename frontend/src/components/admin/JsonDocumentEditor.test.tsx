import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { JsonDocumentEditor } from "./JsonDocumentEditor"
import { validateJsonDocument } from "./json-document-validation"

describe("validateJsonDocument", () => {
  it("accepts objects and rejects arrays and malformed JSON", () => {
    expect(validateJsonDocument('{"name":"sample"}')).toEqual({
      valid: true,
      document: { name: "sample" },
    })
    expect(validateJsonDocument("[]")).toEqual({
      valid: false,
      message: "The sample document must be a JSON object.",
      line: 1,
      column: 1,
      diagnostics: [
        {
          message: "The sample document must be a JSON object.",
          line: 1,
          column: 1,
        },
      ],
    })

    const malformed = validateJsonDocument('{\n  "name":\n}')
    expect(malformed.valid).toBe(false)
    if (!malformed.valid) {
      expect(malformed.message).toMatch(/JSON|line|position/i)
      expect(malformed.line).toBe(3)
      expect(malformed.column).toBe(1)
      expect(malformed.diagnostics).toEqual(
        expect.arrayContaining([expect.objectContaining({ line: 3, column: 1 })]),
      )
    }
  })
})

describe("JsonDocumentEditor", () => {
  it("formats, resets, and saves only a valid changed object", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <JsonDocumentEditor
        document={{ name: "sample", paired: false }}
        onCancel={vi.fn()}
        onSave={onSave}
      />,
    )

    const editor = screen.getByRole("textbox", { name: "Sample JSON" })
    const save = screen.getByRole("button", { name: "Save sample" })
    expect(save).toBeDisabled()

    fireEvent.change(editor, { target: { value: '{"name":"changed"}' } })
    expect(save).toBeEnabled()
    await user.click(screen.getByRole("button", { name: "Format JSON" }))
    expect(editor).toHaveValue('{\n  "name": "changed"\n}')

    await user.click(save)
    expect(onSave).toHaveBeenCalledWith({ name: "changed" })

    await user.click(screen.getByRole("button", { name: "Reset" }))
    expect(editor).toHaveValue('{\n  "name": "sample",\n  "paired": false\n}')
    expect(save).toBeDisabled()
  })

  it("reports invalid roots and exposes a read-only mode", () => {
    const { rerender } = render(
      <JsonDocumentEditor document={{ name: "sample" }} onCancel={vi.fn()} onSave={vi.fn()} />,
    )
    const editor = screen.getByRole("textbox", { name: "Sample JSON" })
    fireEvent.change(editor, { target: { value: "[]" } })
    expect(screen.getByText("The sample document must be a JSON object.")).toBeVisible()
    expect(screen.getByLabelText("JSON diagnostics")).toBeVisible()
    expect(screen.getByText("Line 1:1")).toBeVisible()
    expect(screen.getByRole("button", { name: "Save sample" })).toBeDisabled()

    rerender(
      <JsonDocumentEditor readOnly document={{ name: "sample" }} onCancel={vi.fn()} onSave={vi.fn()} />,
    )
    expect(screen.getByRole("textbox", { name: "Sample JSON" })).toHaveAttribute("readonly")
    expect(screen.queryByRole("button", { name: "Save sample" })).not.toBeInTheDocument()
  })
})
