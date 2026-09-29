import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { RecordProvenance } from "./RecordProvenance"
import { adminExportValue, adminFields } from "./resource-list"

describe("Administrative record provenance", () => {
  it("identifies system ownership without presenting the installer as a user creator", () => {
    render(<RecordProvenance record={{ system_managed: true, created_by: "bootstrap" }} />)
    expect(screen.getByText("System")).toBeVisible()
    expect(screen.queryByText("bootstrap")).not.toBeInTheDocument()
  })
  it("shows a recorded creator", () => {
    render(<RecordProvenance record={{ created_by: "test.author" }} />)
    expect(screen.getByText("test.author")).toBeVisible()
  })
  it("does not infer missing provenance", () => {
    render(<RecordProvenance record={{}} />)
    expect(screen.getByText("Unknown")).toBeVisible()
  })
  it("includes one provenance column and exports its displayed value", () => {
    const row = { asp_id: "panel", created_by: "test.author" }
    expect(adminFields("asp", [row]).filter((field) => ["record_provenance", "created_by", "installed_by"].includes(field))).toEqual(["record_provenance"])
    expect(adminExportValue("record_provenance", row)).toBe("test.author")
    expect(adminExportValue("record_provenance", { system_managed: true })).toBe("System")
    expect(adminExportValue("record_provenance", {})).toBe("Unknown")
  })
})
