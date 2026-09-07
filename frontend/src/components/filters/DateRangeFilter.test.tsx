import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import {
  DateRangeFilter,
} from "./DateRangeFilter"
import {
  dateRangeLabel,
  parseDateRangePreset,
  resolveDateRange,
} from "./date-range"

describe("DateRangeFilter", () => {
  it("normalizes presets and exposes their display labels", () => {
    expect(parseDateRangePreset("7d")).toBe("7d")
    expect(parseDateRangePreset("unsupported")).toBe("all")
    expect(dateRangeLabel("30d")).toBe("Last 30 days")
  })

  it("resolves rolling and inclusive custom date boundaries", () => {
    const now = new Date("2026-08-26T12:00:00.000Z")
    expect(resolveDateRange("1d", "", "", now)).toEqual({
      addedFrom: "2026-08-25T12:00:00.000Z",
      addedUntil: null,
    })

    const custom = resolveDateRange("custom", "2026-08-01", "2026-08-03", now)
    const from = new Date(custom.addedFrom as string)
    const until = new Date(custom.addedUntil as string)
    expect([from.getFullYear(), from.getMonth() + 1, from.getDate()]).toEqual([2026, 8, 1])
    expect([until.getFullYear(), until.getMonth() + 1, until.getDate()]).toEqual([2026, 8, 4])
  })

  it("renders custom controls and prevents an invalid range from being applied", async () => {
    const user = userEvent.setup()
    const onPresetChange = vi.fn()
    const onApply = vi.fn()
    const { rerender } = render(
      <DateRangeFilter
        preset="all"
        from=""
        until=""
        onPresetChange={onPresetChange}
        onFromChange={vi.fn()}
        onUntilChange={vi.fn()}
        onApply={onApply}
      />,
    )

    await user.selectOptions(screen.getByLabelText("Date added"), "custom")
    expect(onPresetChange).toHaveBeenCalledWith("custom")

    rerender(
      <DateRangeFilter
        preset="custom"
        from="2026-08-03"
        until="2026-08-01"
        onPresetChange={onPresetChange}
        onFromChange={vi.fn()}
        onUntilChange={vi.fn()}
        onApply={onApply}
      />,
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Apply dates" })).toBeDisabled()
  })
})
