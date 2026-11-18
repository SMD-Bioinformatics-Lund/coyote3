// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { AppLoader } from "./AppLoader"

it("exposes the loading operation to assistive technology", () => {
  render(<AppLoader label="Loading published tests" />)
  const indicator = screen.getByRole("status", { name: "Loading published tests" })
  expect(indicator).toHaveTextContent("Loading published tests")
})
