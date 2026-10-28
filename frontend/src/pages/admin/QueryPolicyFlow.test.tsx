import { fireEvent, render, screen, within } from "@testing-library/react"
import { expect, it } from "vitest"
import { QueryPolicyFlow, type PolicyResolution } from "./QueryPolicyFlow"

const parent = { id: "old-rule", mode: "exclude", genes: ["TP53"] }
const added = { id: "new-rule", mode: "admit", genes: ["CEBPA"] }
const policy: PolicyResolution = {
  evidence_mode: "case_only", exceptions: [added],
  lineage: [
    { source: "default", version: null, population_frequency_fields: ["gnomad_frequency"], content: { evidence_mode: "paired", exceptions: [], exception_mode: "replace" } },
    { source: "group", version: 1, content: { evidence_mode: null, exceptions: [parent], exception_mode: "replace" } },
    { source: "preview", version: null, content: { evidence_mode: "case_only", exceptions: [added], exception_mode: "replace" } },
  ],
}

it("shows application gates and replaced rules while excluding old rules from the final flow", () => {
  render(<QueryPolicyFlow value={policy} analysis="snv" />)
  fireEvent.click(screen.getByText("Sources and overridden rules"))
  expect(screen.getByText("Application defaults")).toBeVisible()
  expect(screen.getByText("Replaced by Selected version")).toBeVisible()
  expect(screen.getByText("Exceptions replaced by Selected version")).toBeVisible()
  const summary = screen.getAllByText("old-rule")[0].closest("summary")!
  fireEvent.click(summary)
  expect(screen.getByText("TP53")).toBeInTheDocument()
  const flow = screen.getByRole("region", { name: "Final selection flow" })
  expect(within(flow).queryByText("old-rule")).not.toBeInTheDocument()
  expect(within(flow).getByText("new-rule")).toBeVisible()
  expect(within(flow).getByText("gnomad_frequency")).toBeVisible()
  expect(within(flow).queryByRole("region", { name: "Control evidence" })).not.toBeInTheDocument()
  expect(within(flow).getByRole("region", { name: "Sample boundary" })).toBeVisible()
})

it("preserves inherited exceptions in extend mode and shows paired control alternatives", () => {
  render(<QueryPolicyFlow value={{ ...policy, evidence_mode: "paired", exceptions: [parent, added], lineage: [policy.lineage[0], policy.lineage[1], { ...policy.lineage[2], content: { evidence_mode: null, exceptions: [added], exception_mode: "extend" } }] }} analysis="snv" />)
  expect(screen.queryByText("Exceptions replaced by Selected version")).not.toBeInTheDocument()
  const flow = screen.getByRole("region", { name: "Final selection flow" })
  expect(within(flow).getByText("old-rule")).toBeVisible()
  expect(within(flow).getByText("new-rule")).toBeVisible()
  expect(within(flow).getByRole("region", { name: "Control evidence" })).toBeVisible()
})

it("shows an empty admission-only branch as matching no findings", () => {
  render(<QueryPolicyFlow value={{ ...policy, evidence_mode: "exception_only", exceptions: [] }} analysis="snv" />)
  const flow = screen.getByRole("region", { name: "Final selection flow" })
  expect(within(flow).getByText("No admission exceptions: no findings can pass.")).toBeVisible()
  expect(within(flow).queryByRole("region", { name: "Ordinary evidence" })).not.toBeInTheDocument()
})

it("marks the previous published leaf as replaced even when the selected version inherits", () => {
  render(<QueryPolicyFlow value={{ ...policy, evidence_mode: "paired", exceptions: [], lineage: [policy.lineage[0], { ...policy.lineage[1], superseded_by_preview: true }, { source: "preview", version: null, content: { evidence_mode: null, exceptions: null } }] }} analysis="snv" />)
  fireEvent.click(screen.getByText("Sources and overridden rules"))
  expect(screen.getByText("Published version replaced in this preview. Inherited settings come from its ancestors.")).toBeVisible()
  expect(screen.getByText("Exceptions replaced by Selected version")).toBeVisible()
  const flow = screen.getByRole("region", { name: "Final selection flow" })
  expect(within(flow).queryByText("old-rule")).not.toBeInTheDocument()
  expect(within(flow).getByRole("region", { name: "Control evidence" })).toBeVisible()
})

it("keeps somatic replacements separate from germline source layers", () => {
  render(<QueryPolicyFlow value={{ ...policy, lineage: [...policy.lineage, { source: "default", version: null, application: "somatic_snv_exceptions", content: { evidence_mode: "exception_only", exceptions: [parent], exception_mode: "replace" } }] }} analysis="snv" />)
  fireEvent.click(screen.getByText("Sources and overridden rules"))
  expect(screen.getAllByText("Exceptions replaced by Selected version")).toHaveLength(1)
  expect(screen.getByText("Germline exception branch; does not replace somatic evidence.")).toBeVisible()
})

it.each(["cnv", "translocation", "fusion"])("shows %s application selection instead of SNV evidence", analysis => {
  render(<QueryPolicyFlow value={{ ...policy, evidence_mode: null }} analysis={analysis} />)
  const flow = screen.getByRole("region", { name: "Final selection flow" })
  expect(within(flow).queryByText("gnomad_frequency")).not.toBeInTheDocument()
  expect(within(flow).getByText("new-rule")).toBeVisible()
  expect(within(flow).getByRole("region", { name: "Sample boundary" })).toBeVisible()
})
