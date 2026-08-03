import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { GlobalRichTooltip } from "./global-rich-tooltip"

describe("GlobalRichTooltip", () => {
  it("upgrades button titles and restores the native hint after hover", () => {
    render(
      <>
        <button title="Download the complete table" aria-label="Export CSV" data-tooltip-context="Table action">
          Export
        </button>
        <GlobalRichTooltip />
      </>,
    )

    const button = screen.getByRole("button", { name: "Export CSV" })
    fireEvent.pointerOver(button, { clientX: 20, clientY: 20 })
    expect(screen.getByRole("tooltip")).toHaveTextContent("Table action")
    expect(screen.getByRole("tooltip")).toHaveTextContent("Export CSV")
    expect(screen.getByRole("tooltip")).toHaveTextContent("Download the complete table")
    expect(button).not.toHaveAttribute("title")

    fireEvent.pointerOut(button)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    expect(button).toHaveAttribute("title", "Download the complete table")
  })

  it("supports keyboard focus and ignores iframe accessibility titles", () => {
    render(
      <>
        <a href="/details" title="Open the finding detail">Details</a>
        <iframe title="Clinical report preview" />
        <GlobalRichTooltip />
      </>,
    )

    fireEvent.focus(screen.getByRole("link", { name: "Details" }))
    expect(screen.getByRole("tooltip")).toHaveTextContent("Open the finding detail")
    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()

    fireEvent.pointerOver(screen.getByTitle("Clinical report preview"), { clientX: 20, clientY: 20 })
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })
})
