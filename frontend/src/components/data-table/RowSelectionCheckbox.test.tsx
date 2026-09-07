import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { RowSelectionCheckbox } from "./RowSelectionCheckbox"

describe("RowSelectionCheckbox", () => {
  it("sets the native indeterminate state without changing checked state", () => {
    render(
      <RowSelectionCheckbox
        checked={false}
        indeterminate
        onChange={vi.fn()}
        label="Select all rows"
      />,
    )

    const checkbox = screen.getByRole("checkbox", { name: "Select all rows" }) as HTMLInputElement
    expect(checkbox.checked).toBe(false)
    expect(checkbox.indeterminate).toBe(true)
  })

  it("forwards changes through the shared checkbox contract", () => {
    const onChange = vi.fn()
    render(
      <RowSelectionCheckbox
        checked={false}
        onChange={onChange}
        label="Select row"
      />,
    )

    screen.getByRole("checkbox", { name: "Select row" }).click()
    expect(onChange).toHaveBeenCalledOnce()
  })
})
