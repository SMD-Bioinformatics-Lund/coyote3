import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { DetailNavigationButton } from "./DetailNavigationButton"

describe("DetailNavigationButton", () => {
  it("renders an accessible internal detail link with the shared circular style", () => {
    render(
      <MemoryRouter>
        <DetailNavigationButton
          to="/samples/sample-1/variant/variant-1"
          state={{ from: "/samples/sample-1" }}
          label="View variant details"
          description="Open the complete variant record."
        />
      </MemoryRouter>,
    )

    const link = screen.getByRole("link", { name: "View variant details" })
    expect(link).toHaveAttribute("href", "/samples/sample-1/variant/variant-1")
    expect(link).toHaveClass("detail-navigation-button")
    expect(link.querySelector("svg")).toBeInTheDocument()
  })
})
