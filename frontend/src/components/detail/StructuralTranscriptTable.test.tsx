import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { StructuralTranscriptTable, type StructuralTranscriptRow } from "./StructuralTranscriptTable"

const rows: StructuralTranscriptRow[] = [{
  annotation_key: "first",
  annotation: { Annotation: ["gene_fusion"] },
  partners: [
    { gene: "BCR", transcript: "ENST000001", mane_flags: ["ensembl_mane_select"] },
    { gene: "ABL1", transcript: "ENST000002", mane_flags: [] },
  ],
}, {
  annotation_key: "second", annotation: {},
  partners: [{ gene: "BCR", transcript: "ENST000003", mane_flags: [] }],
}]

describe("SnpEff transcript combinations", () => {
  it("separates partners, displays MANE evidence and selects the exact combination", async () => {
    const select = vi.fn()
    render(<StructuralTranscriptTable rows={rows} selectedKey="first" canSelect pending={false}
      onSelect={select} translations={{}} />)
    expect(screen.getByText("Gene 1")).toBeVisible()
    expect(screen.getByText("Transcript 2")).toBeVisible()
    expect(screen.getByText("ABL1")).toBeVisible()
    expect(screen.getByText("Ensembl MANE Select")).toBeVisible()
    expect(screen.getByText("Selected")).toBeVisible()
    await userEvent.click(screen.getByRole("button", { name: "Select ENST000003" }))
    expect(select).toHaveBeenCalledWith("second")
  })
  it("keeps transcript evidence visible without selection permission", () => {
    render(<StructuralTranscriptTable rows={rows} selectedKey="first" canSelect={false}
      pending={false} onSelect={vi.fn()} translations={{}} />)
    expect(screen.queryByRole("button", { name: /Select/ })).not.toBeInTheDocument()
    expect(screen.getByText("ENST000003")).toBeVisible()
  })
})
