import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AppErrorBoundary } from "./AppErrorBoundary"

function BrokenView(): never {
  throw new Error("render failed")
}

describe("AppErrorBoundary", () => {
  it("replaces a crashed view with a recoverable error screen", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined)

    render(
      <AppErrorBoundary>
        <BrokenView />
      </AppErrorBoundary>,
    )

    expect(screen.getByRole("heading", { name: "This view could not be displayed" })).toBeVisible()
    expect(screen.getByRole("button", { name: "Reload page" })).toBeVisible()

    consoleError.mockRestore()
  })
})
