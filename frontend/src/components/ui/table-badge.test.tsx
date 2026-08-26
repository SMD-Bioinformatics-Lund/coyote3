import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { InfoBadge, TableBadge } from "@/components/ui/table-badge"

describe("TableBadge", () => {
  it("applies the shared compact table badge contract", () => {
    render(<TableBadge className="bg-pass/10">Ready</TableBadge>)

    const badge = screen.getByText("Ready")
    expect(badge).toHaveAttribute("data-slot", "table-badge")
    expect(badge).toHaveClass("type-badge", "min-h-6", "rounded-md", "px-2", "py-0.5", "bg-pass/10")
  })

  it("can render an external link without changing badge geometry", () => {
    render(
      <TableBadge as="a" href="https://example.test" target="_blank">
        Reference
      </TableBadge>,
    )

    expect(screen.getByRole("link", { name: "Reference" })).toHaveAttribute("href", "https://example.test")
  })

  it("provides a smaller marker for clinical information columns", () => {
    render(<InfoBadge>OKB</InfoBadge>)

    expect(screen.getByText("OKB")).toHaveClass(
      "h-3",
      "min-h-3",
      "min-w-2.5",
      "px-0.5",
      "text-[0.4375rem]",
      "shadow-none",
    )
  })
})
