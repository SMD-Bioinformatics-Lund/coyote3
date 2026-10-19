import { act, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

const provider = vi.hoisted(() => vi.fn(({ children }: { children: ReactNode }) => <section data-testid="next-theme-provider">{children}</section>))
const preference = vi.hoisted(() => ({ theme: "system" }))
vi.mock("next-themes", () => ({ ThemeProvider: provider, useTheme: () => preference }))

import { ThemeProvider } from "./theme-provider"
import { scheduledTheme } from "@/lib/theme-schedule"

afterEach(() => { vi.useRealTimers(); preference.theme = "system" })

describe("ThemeProvider", () => {
  it.each([[6, 59, "dark"], [7, 0, "light"], [18, 59, "light"], [19, 0, "dark"], [0, 0, "dark"]])(
    "resolves local time %s:%s as %s", (hour, minute, expected) => {
      expect(scheduledTheme(new Date(2026, 9, 19, Number(hour), Number(minute)))).toBe(expected)
    },
  )

  it("updates automatic mode at the boundary and releases manual preferences", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 19, 18, 59, 50))
    preference.theme = "auto"
    const { rerender } = render(<ThemeProvider><p>Content</p></ThemeProvider>)
    expect(provider).toHaveBeenLastCalledWith(expect.objectContaining({ forcedTheme: "light" }), undefined)
    act(() => vi.advanceTimersByTime(30_000))
    expect(provider).toHaveBeenLastCalledWith(expect.objectContaining({ forcedTheme: "dark" }), undefined)
    preference.theme = "light"
    rerender(<ThemeProvider><p>Content</p></ThemeProvider>)
    expect(provider).toHaveBeenLastCalledWith(expect.objectContaining({ forcedTheme: undefined }), undefined)
  })

  it("rechecks the clock after returning to a suspended tab", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 19, 12))
    preference.theme = "auto"
    render(<ThemeProvider><p>Content</p></ThemeProvider>)
    vi.setSystemTime(new Date(2026, 9, 19, 22))
    act(() => window.dispatchEvent(new Event("focus")))
    expect(provider).toHaveBeenLastCalledWith(expect.objectContaining({ forcedTheme: "dark" }), undefined)
  })
  it("delegates theme behavior and configuration to next-themes", () => {
    render(
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem storageKey="coyote3-theme">
        <p>Application content</p>
      </ThemeProvider>,
    )

    expect(screen.getByTestId("next-theme-provider")).toContainElement(screen.getByText("Application content"))
    expect(provider).toHaveBeenCalledWith(
      expect.objectContaining({
        attribute: "class",
        defaultTheme: "system",
        enableSystem: true,
        storageKey: "coyote3-theme",
      }),
      undefined,
    )
  })
})
