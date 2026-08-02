import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

const setTheme = vi.hoisted(() => vi.fn())
const useTheme = vi.hoisted(() => vi.fn())
vi.mock("next-themes", () => ({ useTheme }))

import { ThemeToggle } from "./theme-toggle"

describe("ThemeToggle", () => {
  it.each([
    ["light", "dark"],
    ["dark", "light"],
  ])("switches %s to %s", async (current, expected) => {
    useTheme.mockReturnValue({ theme: current, setTheme })
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole("button", { name: "Toggle theme" }))
    expect(setTheme).toHaveBeenCalledWith(expected)
  })
})
