import { render, screen, within } from "@testing-library/react"
import { expect, it } from "vitest"
import { AppLoader } from "./AppLoader"

it("shows the operation label visually as well as to assistive technology", () => {
  render(<AppLoader label="Loading published tests" />)
  const indicator = screen.getByRole("status", { name: "Loading published tests" })
  expect(within(indicator).getByText("Loading published tests")).toBeVisible()
})
