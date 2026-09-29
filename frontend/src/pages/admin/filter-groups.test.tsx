import { render, screen, within } from "@testing-library/react"
import { expect, it } from "vitest"
import { StructuredObjectField } from "./resource-form"

it("separates applicable filter groups with named sections and theme headers", () => {
  render(<StructuredObjectField field={{ display_type: "filters-structured", groups: [
    { title: "SNV thresholds", requires_analysis: ["SNV"], fields: [{ key: "somatic.snv.min_depth", label: "Minimum depth", type: "int", default: 100 }] },
    { title: "CNV thresholds", requires_analysis: ["CNV"], fields: [] },
  ] }} value={{}} onChange={() => {}} formValues={{ analysis_types: ["SNV"] }} />)
  const group = screen.getByRole("group", { name: "SNV thresholds" })
  expect(within(group).getByRole("heading")).toHaveClass("bg-muted", "border-primary")
  expect(within(group).getByRole("spinbutton")).toHaveValue(100)
  expect(screen.queryByRole("group", { name: "CNV thresholds" })).toBeNull()
})

it("explains when no filter groups apply", () => {
  render(<StructuredObjectField field={{ display_type: "filters-structured", groups: [] }} value={{}} onChange={() => {}} />)
  expect(screen.getByRole("status")).toHaveTextContent("No filter groups apply")
})

it("combines thresholds and scope by category without mixing clinical intents", () => {
  render(<StructuredObjectField field={{ display_type: "filters-structured", groups: [
    { title: "SNV thresholds", category: "Somatic SNV", requires_intent: ["somatic"], fields: [{ key: "somatic.snv.min_depth", label: "Minimum depth", type: "int", default: 100 }] },
    { title: "CNV thresholds", category: "Somatic CNV", fields: [{ key: "somatic.cnv.min_size", label: "Minimum size", type: "int", default: 50 }] },
    { title: "SNV scope", category: "Somatic SNV", requires_intent: ["somatic"], fields: [{ key: "somatic.snv.snvlists", label: "Gene lists", type: "checkbox-group", options: ["Synthetic list"] }] },
    { title: "Germline thresholds", category: "Germline SNV", requires_intent: ["germline"], fields: [{ key: "germline.snv.min_depth", label: "Germline depth", type: "int", default: 30 }] },
  ] }} value={{}} onChange={() => {}} formValues={{ analysis_intents: ["somatic", "germline"] }} />)
  const snv = screen.getByRole("group", { name: "Somatic SNV" })
  expect(within(snv).getByRole("spinbutton")).toHaveValue(100)
  expect(within(snv).getByText("Synthetic list")).toBeInTheDocument()
  expect(within(snv).queryByText("Minimum size")).toBeNull()
  expect(within(screen.getByRole("group", { name: "Germline SNV" })).getByRole("spinbutton")).toHaveValue(30)
  expect(screen.getAllByRole("heading")).toHaveLength(3)
})
