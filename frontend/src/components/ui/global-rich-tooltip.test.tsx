import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AppTooltip } from "./app-tooltip"
import { GlobalRichTooltip } from "./global-rich-tooltip"

describe("GlobalRichTooltip", () => {
  it("retains an existing accessible description while the tooltip is open", () => {
    render(<><p id="help">Required context</p><button aria-describedby="help" title="Hint">Action</button><GlobalRichTooltip /></>)
    const button = screen.getByRole("button")
    fireEvent.focus(button)
    expect(button.getAttribute("aria-describedby")?.split(" ")).toContain("help")
  })
  it("closes when its target is removed", async () => {
    const view = render(<><button title="Hint">Action</button><GlobalRichTooltip /></>)
    fireEvent.pointerOver(screen.getByRole("button"))
    view.rerender(<>{null}<GlobalRichTooltip /></>)
    await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument())
  })
  it("updates an active hint when the title changes", async () => {
    const view = render(<><button title="Old hint">Action</button><GlobalRichTooltip /></>)
    fireEvent.pointerOver(screen.getByRole("button"))
    view.rerender(<><button title="New hint">Action</button><GlobalRichTooltip /></>)
    await waitFor(() => expect(screen.getByRole("tooltip")).toHaveTextContent("New hint"))
  })
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
