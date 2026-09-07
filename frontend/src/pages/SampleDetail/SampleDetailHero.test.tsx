import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { renderWithRouter } from "@/test/render"

import { SampleDetailHero } from "./SampleDetailHero"

const sample = {
  name: "CASE_001",
  case_id: "CASE_001",
  control_id: "CONTROL_001",
  paired: true,
  ingest_status: "ready",
  environment: "production",
  asp_id: "hema_gmsv1",
  time_added: "2026-07-31T08:00:00Z",
  case: { ffpe: true, purity: 0.72 },
}

describe("SampleDetailHero", () => {
  it("presents the sample identity, state, biomarkers, purity, and material in one hero", async () => {
    const user = userEvent.setup()
    renderWithRouter(
      <SampleDetailHero
        sample={sample}
        context={{
          biomarkers: [{
            MSIS: { per: 0.12, tot: 100, som: 12 },
            HRD: { sum: 21, tai: 6, hrd: 7, lst: 8 },
          }],
        }}
      />,
    )

    expect(screen.getByRole("heading", { name: "CASE_001" })).toBeVisible()
    expect(screen.getByText("hema_gmsv1 • production")).toBeVisible()
    expect(screen.getByText("Case")).toBeVisible()
    expect(screen.getByText("Control")).toBeVisible()
    expect(screen.getByText("CONTROL_001")).toBeVisible()
    expect(screen.getByText("Added")).toBeVisible()
    expect(screen.getByText("Paired")).toBeVisible()
    expect(screen.getByText("ready")).toBeVisible()
    expect(screen.getByText("Unreported")).toBeVisible()
    expect(screen.getByText("MSI (Single):")).toBeVisible()
    expect(screen.getByText("0.12%")).toBeVisible()
    expect(screen.getByText("HRD:")).toBeVisible()
    expect(screen.getByText("21")).toBeVisible()
    expect(screen.getByText("Purity:")).toBeVisible()
    expect(screen.getByText("72%")).toBeVisible()
    expect(screen.getByText("FFPE:")).toBeVisible()

    await user.hover(screen.getByText("MSI (Single):"))
    expect(screen.getByText("Total: 100; Somatic: 12")).toBeVisible()
  })

  it("does not create optional metric badges when the sample has no metric data", () => {
    renderWithRouter(
      <SampleDetailHero
        sample={{ ...sample, paired: false, case: { ffpe: false, purity: null } }}
        context={{ biomarkers: null }}
      />,
    )

    expect(screen.getByText("Unpaired")).toBeVisible()
    expect(screen.queryByText("MSI (Single):")).not.toBeInTheDocument()
    expect(screen.queryByText("Purity:")).not.toBeInTheDocument()
    expect(screen.queryByText("FFPE:")).not.toBeInTheDocument()
  })
})
