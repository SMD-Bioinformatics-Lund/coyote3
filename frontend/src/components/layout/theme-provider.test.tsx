import { render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

const provider = vi.hoisted(() => vi.fn(({ children }: { children: ReactNode }) => <section data-testid="next-theme-provider">{children}</section>))
vi.mock("next-themes", () => ({ ThemeProvider: provider }))

import { ThemeProvider } from "./theme-provider"

describe("ThemeProvider", () => {
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
