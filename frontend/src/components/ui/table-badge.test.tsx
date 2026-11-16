// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { TableBadge } from "@/components/ui/table-badge"

describe("TableBadge", () => {
  it("can render an accessible external link", () => {
    render(
      <TableBadge as="a" href="https://example.test" target="_blank">
        Reference
      </TableBadge>,
    )

    expect(screen.getByRole("link", { name: "Reference" })).toHaveAttribute("href", "https://example.test")
  })
})
