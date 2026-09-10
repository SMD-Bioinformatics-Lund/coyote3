import { useState } from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { CheckboxGroup } from "./resource-form"

function AssayChoices() {
  const [asp, setAsp] = useState("dna")
  const [analysis, setAnalysis] = useState(["SNV", "CNV"])
  const [report, setReport] = useState(["SNV", "CNV"])
  return <>
    <button onClick={() => setAsp("empty")}>ASP without files</button>
    <fieldset><legend>Analysis</legend><CheckboxGroup
      field={{ options: ["SNV", "CNV"], show_unavailable_options: true,
        options_by_field: { field: "asp_id", values: { dna: ["SNV"], empty: [] } } }}
      value={analysis} onChange={setAnalysis} formValues={{ asp_id: asp }}
    /></fieldset>
    <fieldset><legend>Reporting</legend><CheckboxGroup
      field={{ options: ["SNV", "CNV"], show_unavailable_options: true, options_from_field: "analysis_types" }}
      value={report} onChange={setReport} formValues={{ analysis_types: analysis }}
    /></fieldset>
    <output>{JSON.stringify({ analysis, report })}</output>
  </>
}

describe("ASPC file-dependent choices", () => {
  it("disables missing data and clears stale analysis/report selections after changing ASP", async () => {
    render(<AssayChoices />)
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent('{"analysis":["SNV"],"report":["SNV"]}'))
    screen.getAllByLabelText("CNV").forEach((input) => {
      expect(input).toBeDisabled()
      expect(input).not.toBeChecked()
    })
    await userEvent.setup().click(screen.getByText("ASP without files"))
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent('{"analysis":[],"report":[]}'))
    screen.getAllByRole("checkbox").forEach((input) => expect(input).toBeDisabled())
  })
})
