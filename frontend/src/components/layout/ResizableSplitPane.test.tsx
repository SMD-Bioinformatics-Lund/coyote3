import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ResizableSplitPane } from "./ResizableSplitPane"

describe("ResizableSplitPane", () => {
  it("restores, clamps, changes, and persists keyboard sizes", () => {
    localStorage.setItem("cnv-pane", "95")
    render(
      <ResizableSplitPane storageKey="cnv-pane" primary={<div>Table</div>} secondary={<div>Image</div>} />,
    )
    const separator = screen.getByRole("separator", { name: "Resize panes" })
    expect(separator).toHaveAttribute("aria-valuenow", "80")
    fireEvent.keyDown(separator, { key: "ArrowLeft" })
    expect(separator).toHaveAttribute("aria-valuenow", "78")
    expect(localStorage.getItem("cnv-pane")).toBe("78")
    fireEvent.keyDown(separator, { key: "Home" })
    expect(separator).toHaveAttribute("aria-valuenow", "35")
    fireEvent.keyDown(separator, { key: "End" })
    expect(separator).toHaveAttribute("aria-valuenow", "80")
  })

  it("ignores unrelated keyboard input", () => {
    render(<ResizableSplitPane storageKey="split" initialPrimarySize={60} primary="One" secondary="Two" />)
    const separator = screen.getByRole("separator")
    fireEvent.keyDown(separator, { key: "Enter" })
    expect(separator).toHaveAttribute("aria-valuenow", "60")
    expect(localStorage.getItem("split")).toBeNull()
  })

  it("resizes with a primary pointer drag and persists the final percentage", () => {
    render(<ResizableSplitPane storageKey="pointer-split" initialPrimarySize={60} primary="One" secondary="Two" />)
    const separator = screen.getByRole("separator")
    const container = separator.parentElement!
    Object.defineProperty(container, "getBoundingClientRect", {
      value: () => ({ left: 100, width: 1000 }),
    })
    Object.defineProperty(separator, "setPointerCapture", { value: () => undefined })
    Object.defineProperty(separator, "hasPointerCapture", { value: () => true })
    Object.defineProperty(separator, "releasePointerCapture", { value: () => undefined })

    fireEvent.pointerDown(separator, { pointerId: 1, pointerType: "mouse", button: 0, clientX: 700 })
    expect(separator).toHaveClass("is-dragging")
    expect(separator).toHaveAttribute("aria-valuenow", "60")
    fireEvent.pointerMove(separator, { pointerId: 1, clientX: 850 })
    expect(separator).toHaveAttribute("aria-valuenow", "75")
    fireEvent.pointerUp(separator, { pointerId: 1, clientX: 850 })
    expect(separator).not.toHaveClass("is-dragging")
    expect(localStorage.getItem("pointer-split")).toBe("75")
  })

  it("ignores a non-primary mouse drag", () => {
    render(<ResizableSplitPane storageKey="secondary-button" primary="One" secondary="Two" />)
    const separator = screen.getByRole("separator")
    fireEvent.pointerDown(separator, { pointerId: 2, pointerType: "mouse", button: 2, clientX: 400 })
    expect(separator).not.toHaveClass("is-dragging")
    expect(separator).toHaveAttribute("aria-valuenow", "65")
  })
})
