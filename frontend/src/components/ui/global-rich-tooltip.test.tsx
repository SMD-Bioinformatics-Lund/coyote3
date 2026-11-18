// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { Button } from "./button"
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


describe("shared tooltip coverage and anchoring", () => {
  it("shows icon button names and closes the hint on a readable action", () => {
    render(<><button aria-label="Show password"><svg aria-hidden="true"><path /></svg></button><button>Save changes</button><GlobalRichTooltip /></>)
    fireEvent.pointerOver(screen.getByRole("button", { name: "Show password" }).querySelector("path")!)
    expect(screen.getByRole("tooltip")).toHaveTextContent("Show password")
    fireEvent.pointerOver(screen.getByRole("button", { name: "Save changes" }))
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("does not repeat readable menu, action, badge or field labels on hover or focus", () => {
    render(<>
      <a href="/profile/access-tokens"><svg aria-hidden="true" />Access tokens</a>
      <button title="Save changes">Save changes</button>
      <span data-slot="badge" tabIndex={0}>Active</span>
      <input type="submit" value="Sign in" />
      <label>Username<input defaultValue="synthetic-private-user" /></label>
      <GlobalRichTooltip />
    </>)
    for (const control of [
      screen.getByRole("link"), screen.getByRole("button", { name: "Save changes" }),
      screen.getByText("Active"), screen.getByRole("button", { name: "Sign in" }),
      screen.getByLabelText("Username"),
    ]) {
      fireEvent.pointerOver(control)
      fireEvent.focus(control)
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    }
  })

  it("retains hints for icons whose labels are only available to screen readers", () => {
    render(<><button><svg /><span className="sr-only">Open navigation</span></button><GlobalRichTooltip /></>)
    fireEvent.focus(screen.getByRole("button", { name: "Open navigation" }))
    expect(screen.getByRole("tooltip")).toHaveTextContent("Open navigation")
  })

  it("reveals a clipped caption but stops repeating it when there is room to read it", () => {
    render(<><button title="Long navigation label"><span className="truncate" style={{ overflowX: "hidden" }}>Long navigation label</span></button><GlobalRichTooltip /></>)
    const caption = screen.getByText("Long navigation label")
    let availableWidth = 80
    Object.defineProperties(caption, {
      clientWidth: { get: () => availableWidth },
      clientHeight: { value: 20 },
      scrollWidth: { value: 180 },
      scrollHeight: { value: 20 },
    })
    fireEvent.pointerOver(caption)
    expect(screen.getByRole("tooltip")).toHaveTextContent("Long navigation label")
    fireEvent.pointerOut(caption)
    availableWidth = 240
    fireEvent.pointerOver(caption)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("uses form labels and help text without copying entered values into hints", () => {
    render(<><label htmlFor="password">Password</label><input id="password" type="password" defaultValue="synthetic-secret" aria-describedby="password-help" /><p id="password-help">Enter your account password.</p><label htmlFor="username">Username</label><input id="username" defaultValue="synthetic-private-user" /><GlobalRichTooltip /></>)
    fireEvent.focus(screen.getByLabelText("Password"))
    expect(screen.getByRole("tooltip")).toHaveTextContent("Password")
    expect(screen.getByRole("tooltip")).toHaveTextContent("Enter your account password.")
    expect(screen.getByRole("tooltip")).not.toHaveTextContent("synthetic-secret")
    fireEvent.focus(screen.getByLabelText("Username"))
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("updates fallback labels when a control changes state", async () => {
    const view = render(<><button aria-label="Show password"><svg /></button><GlobalRichTooltip /></>)
    fireEvent.pointerOver(screen.getByRole("button"))
    view.rerender(<><button aria-label="Hide password"><svg /></button><GlobalRichTooltip /></>)
    await waitFor(() => expect(screen.getByRole("tooltip")).toHaveTextContent("Hide password"))
    expect(screen.getByRole("tooltip")).not.toHaveTextContent("Show password")
  })

  it("does not drag a focused control's hint across the page after the pointer leaves", () => {
    render(<><button aria-label="Theme"><svg /></button><GlobalRichTooltip /></>)
    const button = screen.getByRole("button")
    vi.spyOn(button, "getBoundingClientRect").mockReturnValue({ left: 900, right: 940, top: 8, bottom: 48, width: 40, height: 40 } as DOMRect)
    fireEvent(button, new MouseEvent("pointerover", { bubbles: true, clientX: 920, clientY: 28 }))
    act(() => button.focus())
    fireEvent(button, new MouseEvent("pointerout", { bubbles: true, relatedTarget: document.body }))
    const tooltip = screen.getByRole("tooltip")
    const anchored = { left: tooltip.style.left, top: tooltip.style.top }
    fireEvent(document.body, new MouseEvent("pointermove", { bubbles: true, clientX: 400, clientY: 300 }))
    expect({ left: tooltip.style.left, top: tooltip.style.top }).toEqual(anchored)
    expect(parseFloat(tooltip.style.left)).toBeGreaterThan(800)
    expect(parseFloat(tooltip.style.top)).toBeLessThan(100)
  })

  it("keeps keyboard hints anchored when the pointer is elsewhere", () => {
    render(<><button aria-label="Action"><svg /></button><GlobalRichTooltip /></>)
    const button = screen.getByRole("button")
    vi.spyOn(button, "getBoundingClientRect").mockReturnValue({ left: 400, right: 440, top: 80, bottom: 120, width: 40, height: 40 } as DOMRect)
    act(() => button.focus())
    const position = screen.getByRole("tooltip").getAttribute("style")
    fireEvent(document.body, new MouseEvent("pointermove", { bubbles: true, clientX: 100, clientY: 500 }))
    expect(screen.getByRole("tooltip")).toHaveAttribute("style", position)
    fireEvent.keyDown(button, { key: "Escape" })
    fireEvent.pointerMove(button)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("preserves descriptions added while a hint is open and suppresses touch hints", () => {
    render(<><p id="help">Help</p><p id="validation">Validation</p><button aria-describedby="help">Save</button><GlobalRichTooltip /></>)
    const button = screen.getByRole("button")
    fireEvent.focus(button)
    button.setAttribute("aria-describedby", `${button.getAttribute("aria-describedby")} validation`)
    fireEvent.keyDown(button, { key: "Escape" })
    expect(button).toHaveAttribute("aria-describedby", "help validation")
    const touch = new MouseEvent("pointerover", { bubbles: true })
    Object.defineProperty(touch, "pointerType", { value: "touch" })
    fireEvent(button, touch)
    fireEvent.focus(button)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("respects native-title and tooltip opt-outs", () => {
    render(<><button data-native-title="true" title="Native hint">Native</button><button data-tooltip-disabled="true">No hint</button><GlobalRichTooltip /></>)
    fireEvent.pointerOver(screen.getByRole("button", { name: "Native" }))
    expect(screen.getByRole("button", { name: "Native" })).toHaveAttribute("title", "Native hint")
    fireEvent.pointerOver(screen.getByRole("button", { name: "No hint" }))
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("closes managed hints on Escape and does not reopen on ordinary mouse movement", () => {
    render(<AppTooltip content="Useful help"><button>Open</button></AppTooltip>)
    const button = screen.getByRole("button")
    fireEvent.mouseEnter(button)
    expect(screen.getByRole("tooltip")).toBeVisible()
    fireEvent.keyDown(button, { key: "Escape" })
    fireEvent.mouseMove(button)
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })
})


it("explains disabled actions without making them clickable", () => {
  const action = vi.fn()
  render(<><Button disabled onClick={action} title="Select a finding before continuing">Continue</Button><GlobalRichTooltip /></>)
  const button = screen.getByRole("button", { name: "Continue" })
  fireEvent.pointerOver(button)
  expect(screen.getByRole("tooltip")).toHaveTextContent("Select a finding before continuing")
  fireEvent.click(button)
  expect(action).not.toHaveBeenCalled()
  expect(button).toBeDisabled()
})

it("places a keyboard hint using its measured size instead of an estimated height", () => {
  const bottom = window.innerHeight - 80
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return this.getAttribute("role") === "tooltip"
      ? { left: 0, right: 180, top: 0, bottom: 40, width: 180, height: 40 } as DOMRect
      : { left: 400, right: 440, top: bottom - 40, bottom, width: 40, height: 40 } as DOMRect
  })
  render(<AppTooltip content="Short help"><button>Help</button></AppTooltip>)
  fireEvent.focus(screen.getByRole("button"))
  const top = parseFloat(screen.getByRole("tooltip").style.top)
  expect(top).toBeGreaterThan(bottom)
  expect(top + 40).toBeLessThan(window.innerHeight)
})

it("pins keyboard-activated rich help to its control, not the zero-coordinate click", () => {
  render(<AppTooltip content="Help for this control" persistOnClick><button>Help</button></AppTooltip>)
  const button = screen.getByRole("button")
  vi.spyOn(button.parentElement!, "getBoundingClientRect").mockReturnValue({ left: 500, right: 540, top: 200, bottom: 240, width: 40, height: 40 } as DOMRect)
  fireEvent.focus(button)
  fireEvent.click(button, { detail: 0 })
  const tooltip = screen.getByRole("tooltip")
  expect(parseFloat(tooltip.style.left)).toBeGreaterThan(400)
  expect(parseFloat(tooltip.style.top)).toBeGreaterThan(240)
  fireEvent.keyDown(document, { key: "Escape" })
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
})
