import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { RecordProvenance } from "./RecordProvenance"
import { adminExportValue, adminFields } from "./resource-list"

describe("Administrative record provenance", () => {
  it("identifies system ownership without presenting the installer as a user creator", () => {
    render(<RecordProvenance record={{ system_managed: true, created_by: "bootstrap" }} />)
    expect(screen.getByRole("img", { name: "System installed" })).toBeVisible()
    expect(screen.queryByText("bootstrap")).not.toBeInTheDocument()
  })
  it("shows a recorded creator", () => {
    render(<RecordProvenance record={{ created_by: "test.author" }} />)
    expect(screen.getByText("test.author")).toBeVisible()
  })
  it("preserves a creator email instead of inferring system ownership", () => {
    render(<RecordProvenance record={{ system_managed: false, created_by: "author@example.org" }} />)
    expect(screen.getByText("author@example.org")).toBeVisible()
    expect(screen.queryByRole("img", { name: "System installed" })).not.toBeInTheDocument()
  })
  it("does not infer missing provenance", () => {
    render(<RecordProvenance record={{}} />)
    expect(screen.getByText("Unknown")).toBeVisible()
  })
  it("includes one provenance column and exports its displayed value", () => {
    const row = { asp_id: "panel", created_by: "test.author", system_managed: false }
    expect(adminFields(["asp_id", "created_by", "system_managed"], [row]).filter((field) => ["record_provenance", "created_by", "installed_by", "system_managed"].includes(field))).toEqual(["record_provenance"])
    expect(adminExportValue("record_provenance", row)).toBe("test.author")
    expect(adminExportValue("record_provenance", { system_managed: true })).toBe("System")
    expect(adminExportValue("record_provenance", {})).toBe("Unknown")
  })
  it("does not reintroduce ownership fields when many preferred columns are present", () => {
    const row = {
      asp_id: "demo", display_name: "Demo", asp_category: "dna", asp_group: "demo",
      version: 1, system_managed: true, created_by: "bootstrap", installed_by: "bootstrap",
      record_provenance: "System",
    }
    const fields = adminFields(Object.keys(row), [row])
    expect(fields.filter((field) => ["record_provenance", "system_managed", "created_by", "installed_by"].includes(field)))
      .toEqual(["record_provenance"])
  })
})
