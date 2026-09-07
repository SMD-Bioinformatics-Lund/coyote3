import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ClassicAnalysisFiltersSidebar, FindingsTab } from "./FindingsTab"

vi.mock("./FiltersSidebar", () => ({
  CollapsedFiltersRail: ({
    label,
    onExpand,
    ariaLabel,
  }: {
    label: string
    onExpand: () => void
    ariaLabel?: string
  }) => (
    <div aria-label={label}>
      <button type="button" aria-label={ariaLabel} onClick={onExpand}>
        {label}
      </button>
    </div>
  ),
  FiltersSidebar: ({ activeTab, intent }: { activeTab: string; intent: string }) => (
    <div data-testid={`filters-${activeTab}`}>{intent} filters</div>
  ),
}))
vi.mock("./VariantsTab", () => ({ VariantsTab: ({ header, filterPanel }: any) => <div>{header}{filterPanel}</div> }))
vi.mock("./CNVTab", () => ({ CNVTab: ({ header, filterPanel }: any) => <div>{header}{filterPanel}</div> }))
vi.mock("./FusionsTab", () => ({ FusionsTab: ({ header, filterPanel }: any) => <div>{header}{filterPanel}</div> }))
vi.mock("./TranslocationsTab", () => ({ TranslocationsTab: ({ header, filterPanel }: any) => <div>{header}{filterPanel}</div> }))
vi.mock("./RnaAnalysisTabs", () => ({ RnaAnalysisTab: ({ header }: any) => <div>{header}</div> }))

describe("FindingsTab", () => {
  it("keeps result tables free of inline filter forms", () => {
    render(
      <FindingsTab
        sampleId="S1"
        sections={[{ id: "snvs", label: "Somatic SNVs" }, { id: "cnvs", label: "CNVs" }]}
      />,
    )

    expect(screen.queryByTestId("filters-snvs")).not.toBeInTheDocument()
    expect(screen.queryByTestId("filters-cnvs")).not.toBeInTheDocument()
  })

  it("keeps classic finding filters collapsed until explicitly opened", async () => {
    const user = userEvent.setup()
    render(
      <ClassicAnalysisFiltersSidebar
        sampleId="S1"
        sample={{}}
        sections={[
          { id: "snvs", label: "Somatic SNVs" },
          { id: "cnvs", label: "CNVs" },
          { id: "coverage", label: "Coverage" },
        ]}
      />,
    )

    expect(screen.getByLabelText("All finding filters")).toBeVisible()
    expect(screen.getByLabelText("Finding filters")).toBeVisible()
    expect(screen.queryByTestId("filters-snvs")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Expand finding filters" }))
    expect(screen.getByTestId("filters-snvs")).toBeVisible()
    expect(screen.getByTestId("filters-cnvs")).toBeVisible()
    expect(screen.getByTestId("filters-coverage")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Collapse finding filters" }))
    expect(screen.queryByTestId("filters-snvs")).not.toBeInTheDocument()
  })
})
