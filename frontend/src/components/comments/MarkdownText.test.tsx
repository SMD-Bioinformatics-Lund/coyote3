import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { MarkdownText } from "./MarkdownText"

describe("MarkdownText", () => {
  it("renders formatted safe markdown", () => {
    render(<MarkdownText text="**Important** [source](https://example.test)" className="clinical-note" />)
    expect(screen.getByText("Important").tagName).toBe("STRONG")
    expect(screen.getByRole("link", { name: "source" })).toHaveAttribute("href", "https://example.test")
    expect(screen.getByText("Important").closest("div")).toHaveClass("clinical-note")
  })

  it("renders an empty container for missing text", () => {
    const { container } = render(<MarkdownText />)
    expect(container.firstElementChild).toContainHTML("<p></p>")
  })

  it("renders explicitly escaped markdown syntax as literal text", () => {
    render(<MarkdownText text={"\\*\\*Literal\\*\\*\n\\[not a link\\](https://example.test)"} />)

    expect(screen.getByText(/\*\*Literal\*\*/)).toBeVisible()
    expect(screen.queryByRole("link")).not.toBeInTheDocument()
  })
})
