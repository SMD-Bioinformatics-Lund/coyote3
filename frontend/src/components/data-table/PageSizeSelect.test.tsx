import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { PageSizeSelect } from "./PageSizeSelect"

describe("PageSizeSelect", () => {
  it("uses the shared page-size options and returns a numeric value", async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(<PageSizeSelect value={50} onValueChange={onValueChange} showPageSuffix />)

    const select = screen.getByRole("combobox", { name: "Rows per page" })
    expect(screen.getByRole("option", { name: "100 / page" })).toBeInTheDocument()
    await user.selectOptions(select, "100")
    expect(onValueChange).toHaveBeenCalledWith(100)
  })

  it("supports context-specific option labels", () => {
    render(
      <PageSizeSelect
        value={50}
        onValueChange={() => undefined}
        optionLabel={(value) => `${value} rows`}
      />,
    )

    expect(screen.getByRole("option", { name: "50 rows" })).toBeInTheDocument()
  })
})
