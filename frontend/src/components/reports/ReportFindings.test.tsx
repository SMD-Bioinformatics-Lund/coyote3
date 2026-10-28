import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ReportFindings } from "./ReportFindings"
import { REPORT_SNAPSHOT_SECTIONS } from "./report-snapshot"

describe("ReportFindings", () => {
  it("separates the recorded clinical assessment from producer measurements", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "TMB")!
    render(<ReportFindings analysisType="TMB" columns={section.columns} rows={[
      { result: { TMB: { value: 0, unit: "mut/Mb", clinical_assessment: {
        value: "HIGH", revision: 1, assessed_by: "Synthetic reviewer",
      }, assessment_history: [] } } },
    ]} />)
    expect(screen.getByText("0")).toBeVisible()
    expect(screen.getByText("HIGH")).toBeVisible()
    expect(screen.getByText("TMB clinical assessment")).toBeVisible()
    expect(screen.queryByText("Additional measurements")).not.toBeInTheDocument()
  })

  it("keeps repeated findings and full annotations in separate compact table rows", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "SNV")!
    const annotation = "Synthetic interpretation with a retained annotation tail."
    render(<ReportFindings analysisType="SNV" columns={section.columns} rows={[
      { gene: "FLT3", variant: "p.Lys4Glu", class: 1, text: annotation },
      { gene: "FLT3", variant: "p.Lys4Glu", class: 1, text: "Second synthetic finding" },
      { gene: "FLT3", variant: "p.Lys4Glu", class: 1 },
    ]} />)
    const table = within(screen.getByRole("table", { name: "Small variants" }))
    expect(table.getAllByRole("columnheader").map((header) => header.textContent))
      .toEqual(["Gene", "Variant", "Class", "Text"])
    expect(table.getAllByRole("row")).toHaveLength(4)
    expect(table.getAllByText("FLT3")).toHaveLength(3)
    expect(table.getAllByText("p.Lys4Glu")).toHaveLength(3)
    expect(table.getByText(annotation)).toBeVisible()
    expect(table.getByText("Second synthetic finding")).toBeVisible()
    expect(screen.getByRole("region", { name: "Small variants table" })).toHaveAttribute("tabindex", "0")
  })

  it("retains structural variant fields and zero-valued measurements in their columns", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "CNV")!
    render(<ReportFindings analysisType="CNV" columns={section.columns} rows={[
      { genes: ["TP53", "SYNTHETIC_GENE"], region: "1:10000-20000", size: 10000,
        cnv_type: "loss", ratio: 0, callers: ["cnvkit"] },
    ]} />)
    const table = within(screen.getByRole("table", { name: "Copy-number variants" }))
    const cells = within(table.getAllByRole("row")[1]).getAllByRole("cell")
    expect(cells.map((cell) => cell.textContent))
      .toEqual(["TP53, SYNTHETIC_GENE", "1:10000-20000", "10000", "loss", "0", "cnvkit"])
  })

  it("shows the recorded HRD score and components, including zero and additional fields", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "HRD")!
    render(<ReportFindings analysisType="HRD" columns={section.columns} rows={[
      { result: { HRD: { tai: 0, hrd: 3, lst: 4, sum: 7, other: null } } },
    ]} />)
    expect(screen.getByText("Total score")).toBeVisible()
    expect(screen.getByText("7")).toBeVisible()
    expect(screen.getByText("TAI")).toBeVisible()
    expect(screen.getByText("0")).toBeVisible()
    expect(screen.getByText("Additional measurements")).toBeVisible()
    expect(screen.getByText("other")).toBeInTheDocument()
  })

  it("displays reported MSI percentages without rescaling and distinguishes both methods", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "MSI")!
    render(<ReportFindings analysisType="MSI" columns={section.columns} rows={[
      { result: { MSIS: { tot: 100, som: 0, per: 0 }, MSIP: { tot: 100, som: 1, per: 0.12 } } },
    ]} />)
    const single = within(screen.getByRole("group", { name: "Single MSI" }))
    const paired = within(screen.getByRole("group", { name: "Paired MSI" }))
    expect(single.getByText("0%")).toBeVisible()
    expect(single.getByText("0 / 100")).toBeVisible()
    expect(paired.getByText("0.12%")).toBeVisible()
    expect(paired.getByText("1 / 100")).toBeVisible()
  })

  it("keeps zero TMB beside its source unit and marks missing scores without fabricating values", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "TMB")!
    const { rerender } = render(<ReportFindings analysisType="TMB" columns={section.columns} rows={[
      { result: { TMB: { value: 0, unit: "mut/Mb" } } },
    ]} />)
    expect(screen.getByText("0")).toBeVisible()
    expect(screen.getByText("mut/Mb")).toBeVisible()
    rerender(<ReportFindings analysisType="TMB" columns={section.columns} rows={[
      { result: { TMB: { value: null, unit: "mut/Mb" } } },
    ]} />)
    expect(screen.getByText("-")).toBeVisible()
    expect(screen.queryByText("0")).not.toBeInTheDocument()
  })

  it("shows nested biomarker measurements with labels and preserves zero and missing values", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "HRD")!
    render(<ReportFindings columns={section.columns} rows={[
      { biomarker: "HRD", result: { HRD: { TAI: 0, HRD: 3, LST: 4, sum: 7, other: null } } },
    ]} />)
    expect(screen.getByText("TAI")).toBeVisible()
    expect(screen.getByText("0")).toBeVisible()
    expect(screen.getByText("Total score")).toBeVisible()
    expect(screen.getByText("7")).toBeVisible()
    expect(screen.getByText("other")).toBeVisible()
    expect(screen.getByText("-")).toBeVisible()
  })

  it("keeps single and paired MSI measurement labels distinct", () => {
    const section = REPORT_SNAPSHOT_SECTIONS.find((entry) => entry.type === "MSI")!
    render(<ReportFindings columns={section.columns} rows={[
      { biomarker: "MSI", result: { MSIS: { per: 0 }, MSIP: { per: 1 } } },
    ]} />)
    expect(screen.getByText("MSI single / Percentage")).toBeVisible()
    expect(screen.getByText("MSI paired / Percentage")).toBeVisible()
    expect(screen.getByText("0")).toBeVisible()
    expect(screen.getByText("1")).toBeVisible()
  })
})
