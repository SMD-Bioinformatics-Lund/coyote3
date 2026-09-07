import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { AppLoader } from "@/components/layout/AppLoader"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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

  it("renders form and display primitives with forwarded attributes", async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <div>
        <Label htmlFor="gene">Gene</Label>
        <Input id="gene" placeholder="TP53" />
        <Button variant="outline" onClick={onClick}>Search</Button>
        <Badge variant="secondary">Ready</Badge>
      </div>,
    )

    await user.type(screen.getByLabelText("Gene"), "TP53")
    await user.click(screen.getByRole("button", { name: "Search" }))
    expect(screen.getByLabelText("Gene")).toHaveValue("TP53")
    expect(onClick).toHaveBeenCalledOnce()
    expect(screen.getByText("Ready")).toHaveAttribute("data-slot", "badge")
  })

  it("renders cards, panels, metrics, and the global loading status", () => {
    render(
      <>
        <Card size="sm">
          <CardHeader><CardTitle>Title</CardTitle><CardDescription>Description</CardDescription></CardHeader>
          <CardContent>Content</CardContent>
          <CardFooter>Footer</CardFooter>
        </Card>
        <SurfacePanel title="Panel" description="Context" actions={<button>Action</button>}>Body</SurfacePanel>
        <MetricCard title="Samples" value="12" sub="Ready" />
        <AppLoader label="Loading samples" />
      </>,
    )

    expect(screen.getByText("Title")).toBeVisible()
    expect(screen.getByText("Panel")).toBeVisible()
    expect(screen.getByText("12")).toBeVisible()
    expect(screen.getByRole("status", { name: "Loading samples" })).toBeVisible()
  })
})
