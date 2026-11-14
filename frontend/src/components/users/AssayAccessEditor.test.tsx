import { useState } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { AssayAccessEditor, type AssayGrant } from "./AssayAccessEditor"
import { coerceFieldValue } from "@/pages/admin/resource-list"

it("edits each assay/environment pair independently and removes empty rows", () => {
  const changed = vi.fn()
  function Editor() {
    const [value, setValue] = useState<AssayGrant[]>([
      { asp_id: "assay_a", environments: ["production", "development"] },
      { asp_id: "assay_b", environments: ["production"] },
    ])
    return <AssayAccessEditor value={value} onChange={next => { setValue(next); changed(next) }}
      options={[{ value: "assay_a" }, { value: "assay_b" }]} environments={["production", "development"]} />
  }
  render(<Editor />)
  expect(screen.getByRole("checkbox", { name: "assay_b development" })).not.toBeChecked()
  fireEvent.click(screen.getByRole("checkbox", { name: "assay_a development" }))
  expect(changed).toHaveBeenLastCalledWith([
    { asp_id: "assay_a", environments: ["production"] }, { asp_id: "assay_b", environments: ["production"] },
  ])
  fireEvent.click(screen.getByRole("checkbox", { name: "assay_b production" }))
  expect(changed).toHaveBeenLastCalledWith([{ asp_id: "assay_a", environments: ["production"] }])
})

it("keeps structured grants through managed-form submission instead of flattening them", () => {
  const grants = [{ asp_id: "assay_a", environments: ["production"] }]
  expect(coerceFieldValue({ display_type: "assay-access", data_type: "list" }, grants)).toEqual(grants)
  render(<AssayAccessEditor value={grants} onChange={vi.fn()} environments={["production"]} disabled />)
  expect(screen.getByRole("checkbox", { name: "assay_a production" })).toBeDisabled()
})
