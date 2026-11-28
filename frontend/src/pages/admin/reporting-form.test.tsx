// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useState } from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it, vi } from "vitest"
import { AdminManagedForm } from "./AdminManagedForm"
import { formStateFromSpec, submitPayload } from "./resource-list"
import { specs, type FormSpec } from "./resource-specs"

const analyses = ["SNV", "CNV", "TRANSLOCATION"]
const form: FormSpec = { sections: { "clinical reporting": ["reporting"] }, fields: { reporting: { display_type: "reporting-structured", groups: [
  { title: "Report sections", fields: [
    { key: "report_sections", label: "Report sections", type: "checkbox-group", options: analyses, default: ["SNV"] },
  ] },
  { title: "Reportable tiers", fields: [
    { key: "reportable_tiers.SNV", label: "SNV reportable tiers", type: "checkbox-group", options: ["1", "2", "3", "4"], default: ["1", "2", "3"] },
  ] },
  { title: "Report text", fields: [
    { key: "report_header", label: "Report header", type: "text", default: "Synthetic DNA report" },
    { key: "report_method", label: "Report method", type: "text", default: "Synthetic method" },
    { key: "plots_path", label: "Plots path", type: "text", default: "/tmp" },
    { key: "report_folder", label: "Report folder", type: "text", default: "reports" },
  ] },
  { title: "Summary order", fields: [
    { key: "summary_text_order", label: "Summary text order", type: "list", display_type: "ordered-checkboxes", options: analyses, default: [] },
    { key: "summary_table_order", label: "Summary table order", type: "list", display_type: "ordered-checkboxes", options: analyses, default: [] },
  ] },
] } } }

function Editor({ saved, source = {}, mode = "create" }: {
  saved: (payload: Record<string, unknown>) => void
  source?: Record<string, unknown>
  mode?: "create" | "edit" | "view"
}) {
  const [values, setValues] = useState(() => formStateFromSpec(form, source))
  return <AdminManagedForm mode={mode} spec={specs.aspc} form={form} values={values} setValues={setValues} isSaving={false} error="" onCancel={() => {}} onSave={() => mode !== "view" && saved(submitPayload(form, values, mode))} />
}

it("saves visible reporting defaults when only the method is edited, using either save button", () => {
  const saved = vi.fn()
  render(<Editor saved={saved} />)
  fireEvent.change(screen.getByLabelText("Report method"), { target: { value: "Reviewed method" } })
  const buttons = screen.getAllByRole("button", { name: "Save" })
  expect(buttons).toHaveLength(2)
  for (const button of buttons) fireEvent.click(button)
  expect(saved).toHaveBeenCalledTimes(2)
  expect(saved).toHaveBeenLastCalledWith({ reporting: {
    report_header: "Synthetic DNA report", report_method: "Reviewed method",
    plots_path: "/tmp", report_folder: "reports", report_sections: ["SNV"],
    reportable_tiers: { SNV: ["1", "2", "3"] }, summary_text_order: [], summary_table_order: [],
  } })
})

it("keeps section selection independent of tier headings and checkboxes", async () => {
  const user = userEvent.setup()
  const saved = vi.fn()
  render(<Editor saved={saved} />)
  const sections = within(screen.getByRole("group", { name: "Report sections" }))
  const snv = sections.getByRole("checkbox", { name: "SNV" })
  await user.click(screen.getByText("SNV reportable tiers"))
  expect(snv).toBeChecked()
  await user.click(screen.getByRole("checkbox", { name: "2" }))
  expect(snv).toBeChecked()
  expect(sections.getByRole("checkbox", { name: "CNV" })).not.toBeChecked()
  await user.click(snv)
  expect(screen.queryByRole("group", { name: "SNV reportable tiers" })).not.toBeInTheDocument()
  await user.click(snv)
  expect(screen.getByRole("checkbox", { name: "2" })).not.toBeChecked()
  await user.click(screen.getAllByRole("button", { name: "Save" })[0])
  expect(saved).toHaveBeenLastCalledWith(expect.objectContaining({ reporting: expect.objectContaining({
    report_sections: ["SNV"], reportable_tiers: { SNV: ["1", "3"] },
  }) }))
})

it("loads, reorders and clears text and table priorities independently of enabled sections", async () => {
  const user = userEvent.setup()
  const saved = vi.fn()
  render(<Editor mode="edit" source={{ reporting: { summary_text_order: ["CNV", "SNV"] } }} saved={saved} />)
  const textOrder = within(screen.getByRole("group", { name: "Summary text order" }))
  const tableOrder = within(screen.getByRole("group", { name: "Summary table order" }))
  expect(textOrder.getByRole("button", { name: "Move CNV up" })).toBeDisabled()
  expect(textOrder.getByRole("button", { name: "Move SNV down" })).toBeDisabled()
  await user.click(textOrder.getByRole("checkbox", { name: "TRANSLOCATION" }))
  await user.click(textOrder.getByRole("button", { name: "Move TRANSLOCATION up" }))
  await user.click(tableOrder.getByRole("checkbox", { name: "CNV" }))
  await user.click(tableOrder.getByRole("checkbox", { name: "SNV" }))
  await user.click(tableOrder.getByRole("button", { name: "Move CNV down" }))
  const save = screen.getAllByRole("button", { name: "Save" })[0]
  await user.click(save)
  expect(saved).toHaveBeenLastCalledWith(expect.objectContaining({ reporting: expect.objectContaining({
    report_sections: ["SNV"], summary_text_order: ["CNV", "TRANSLOCATION", "SNV"], summary_table_order: ["SNV", "CNV"],
  }) }))
  for (const checkbox of textOrder.getAllByRole("checkbox", { checked: true })) await user.click(checkbox)
  await user.click(save)
  expect(saved).toHaveBeenLastCalledWith(expect.objectContaining({ reporting: expect.objectContaining({
    summary_text_order: [], summary_table_order: ["SNV", "CNV"],
  }) }))
})

it("shows the saved priorities in order in a read-only configuration", () => {
  render(<Editor mode="view" source={{ reporting: { summary_table_order: ["TRANSLOCATION", "SNV"] } }} saved={vi.fn()} />)
  const tableOrder = within(screen.getByRole("group", { name: "Summary table order" }))
  const checked = tableOrder.getAllByRole("checkbox", { checked: true })
  expect(within(screen.getByRole("group", { name: "Summary text order" })).getByText("Default order")).toBeVisible()
  expect(tableOrder.queryByRole("checkbox", { name: "CNV" })).not.toBeInTheDocument()
  expect(checked[0]).toHaveAccessibleName("TRANSLOCATION")
  expect(checked[1]).toHaveAccessibleName("SNV")
  for (const checkbox of tableOrder.getAllByRole("checkbox")) expect(checkbox).toBeDisabled()
  expect(tableOrder.queryByRole("button")).not.toBeInTheDocument()
})

it("preserves explicit reporting values and does not mutate the source or form defaults", () => {
  const source = { reporting: { report_header: "Reviewed header", report_sections: [], report_method: "", language: null } }
  const state = formStateFromSpec(form, source)
  expect(state.reporting).toMatchObject(source.reporting)
  state.reporting.report_sections.push("SNV")
  expect(source.reporting.report_sections).toEqual([])
  expect(form.fields.reporting.groups![0].fields.find(field => field.key === "report_sections")?.default).toEqual(["SNV"])
})
