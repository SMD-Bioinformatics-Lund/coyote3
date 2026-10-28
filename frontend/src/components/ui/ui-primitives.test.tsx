import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { SegmentedControl } from "@/components/ui/segmented-control"

describe("shared UI primitives", () => {
  it("renders accessible segmented tabs and changes enabled values", async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <SegmentedControl
        ariaLabel="Analysis intent"
        value="somatic"
        onValueChange={onChange}
        items={[
          { value: "somatic", label: "Somatic" },
          { value: "germline", label: "Germline" },
          { value: "disabled", label: "Unavailable", disabled: true },
        ] as const}
      />,
    )

    expect(screen.getByRole("tablist", { name: "Analysis intent" })).toBeVisible()
    expect(screen.getByRole("tab", { name: "Somatic" })).toHaveAttribute("aria-selected", "true")
    await user.click(screen.getByRole("tab", { name: "Germline" }))
    expect(onChange).toHaveBeenCalledWith("germline")
    await user.click(screen.getByRole("tab", { name: "Unavailable" }))
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})
