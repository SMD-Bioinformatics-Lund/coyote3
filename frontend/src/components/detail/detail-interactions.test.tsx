import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ExpandableText } from "./ExpandableText"
import { RotatableImage } from "./RotatableImage"

describe("detail interaction components", () => {
  it("expands, collapses, and copies long text", async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } })
    render(<ExpandableText text="ABCDEFGHIJKLMNOPQRSTUVWXYZ" maxLength={10} />)
    expect(screen.getByText("ABCDEFGHIJ...")).toBeVisible()
    await user.click(screen.getByTitle("Expand"))
    expect(screen.getByText("ABCDEFGHIJKLMNOPQRSTUVWXYZ")).toBeVisible()
    await user.click(screen.getByTitle("Collapse"))
    await user.click(screen.getByTitle("Copy to clipboard"))
    expect(writeText).toHaveBeenCalledWith("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
  })

  it("renders placeholders without interaction controls", () => {
    render(<ExpandableText text="-" />)
    expect(screen.getByText("-")).toBeVisible()
    expect(screen.queryByTitle("Copy to clipboard")).not.toBeInTheDocument()
  })

  it("links images, applies rotation after load, and shows load errors", () => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1000)
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(500)
    const { rerender } = render(<RotatableImage src="/profile.png" alt="CNV profile" href="/full.png" rotation={90} />)
    const image = screen.getByAltText("CNV profile")
    expect(image.closest("a")).toHaveAttribute("href", "/full.png")
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 800 })
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 400 })
    fireEvent.load(image)
    expect(image).toHaveStyle({ transform: "translate(-50%, -50%) rotate(90deg)" })

    rerender(<RotatableImage src="/missing.png" alt="Missing profile" />)
    fireEvent.error(screen.getByAltText("Missing profile"))
    expect(screen.getByText("The CNV profile image could not be loaded.")).toBeVisible()
  })
})
