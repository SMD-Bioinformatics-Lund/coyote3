import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AppTooltip } from "./app-tooltip"
import { GlobalRichTooltip } from "./global-rich-tooltip"

describe("GlobalRichTooltip", () => {
  it("upgrades button titles and suppresses the native hint", () => {
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
    expect(button).not.toHaveAttribute("title")
    expect(button).toHaveAttribute("data-tooltip-content", "Download the complete table")
  })

  it("renders explicit application tooltip metadata", () => {
    render(
      <>
        <AppTooltip
          content="Open the complete clinical finding record."
          label="View details"
          context="Table action"
        >
          <button>Open</button>
        </AppTooltip>
        <GlobalRichTooltip />
      </>,
    )

    fireEvent.mouseEnter(screen.getByRole("button", { name: "Open" }))
    expect(screen.getByRole("tooltip")).toHaveTextContent("Table action")
    expect(screen.getByRole("tooltip")).toHaveTextContent("View details")
    expect(screen.getByRole("tooltip")).toHaveTextContent("Open the complete clinical finding record.")
  })

  it("does not activate an ancestor title inside a managed tooltip subtree", () => {
    render(
      <>
        <span title="Ancestor navigation hint">
          <AppTooltip content="Clinical tier description" label="Tier II">
            <button>Tier 2</button>
          </AppTooltip>
        </span>
        <GlobalRichTooltip />
      </>,
    )

    fireEvent.mouseEnter(screen.getByRole("button", { name: "Tier 2" }))
    const tooltips = screen.getAllByRole("tooltip")
    expect(tooltips).toHaveLength(1)
    expect(tooltips[0]).toHaveTextContent("Clinical tier description")
    expect(tooltips[0]).not.toHaveTextContent("Ancestor navigation hint")
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
