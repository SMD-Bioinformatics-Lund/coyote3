import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RecordProvenance } from "./RecordProvenance"
import { adminCell, adminColumnTitle, adminExportValue, adminFields } from "./resource-list"

describe("Administrative record provenance", () => {
  afterEach(() => vi.useRealTimers())
  it("combines permission display name and identity and removes duplicate name/date columns", () => {
    const row = { permission_id: "cnv:manage", label: "Manage CNVs", description: "Full description", created_on: "2026-10-25T10:00:00Z", updated_on: "2026-10-25T11:00:00Z", created_by: "system", updated_by: "system" }
    render(adminCell("permission_id", row, { primaryIdentifier: true }))
    expect(screen.getByText("Manage CNVs")).toHaveClass("font-semibold")
    expect(screen.getByText("cnv:manage")).toHaveClass("type-meta", "text-muted-foreground")
    expect(adminColumnTitle("permission_id")).toBe("Permission")
    const fields = adminFields(["permission_id", "label", "description", "updated_on"], [row])
    expect(fields).toEqual(["permission_id", "description", "record_provenance", "updated_by"])
  })
  it("wraps descriptive text without truncation", () => {
    const description = "Review findings and apply the supported curation actions.\nPreserve clinical review history."
    const { container } = render(adminCell("description", { description }))
    expect(container.textContent).toBe(description)
    expect(container.firstElementChild).toHaveClass("whitespace-pre-wrap", "break-words")
    expect(container.firstElementChild).not.toHaveClass("truncate")
  })
  it("retains last-login time separately from record attribution", () => {
    const row = { username: "reviewer", fullname: "Example Reviewer", last_login: "2026-10-25T10:00:00Z", updated_on: "2026-10-25T11:00:00Z" }
    const fields = adminFields(["username", "fullname", "last_login", "updated_on"], [row])
    expect(fields).toContain("last_login")
    expect(fields).not.toContain("fullname")
    expect(fields).not.toContain("updated_on")
  })
  it("shows creation time beneath the creator with the exact time on hover", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-10-25T12:00:00Z"))
    render(<RecordProvenance record={{ created_by: "author", created_on: "2026-10-25T11:59:00Z", updated_on: "2026-10-25T12:00:00Z" }} />)
    expect(screen.getByText("author")).toBeVisible()
    expect(screen.getByText("1 min ago").parentElement).toHaveAttribute("title")
    expect(screen.getByText("1 min ago").parentElement).toHaveClass("text-muted-foreground", "type-meta")
  })
  it("shows the updater's timestamp independently of creation time", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-10-25T12:00:00Z"))
    render(<RecordProvenance kind="updated" record={{ created_by: "author", updated_by: "editor", created_on: "2026-10-18T12:00:00Z", updated_on: "2026-10-25T11:00:00Z" }} />)
    expect(screen.getByText("editor")).toBeVisible()
    expect(screen.getByText("1 h ago")).toBeVisible()
    expect(screen.queryByText("author")).not.toBeInTheDocument()
  })
  it("does not use modification time as an unknown creation time", () => {
    render(<RecordProvenance record={{ created_by: "author", updated_on: "2026-10-25T11:00:00Z" }} />)
    expect(screen.getByText("author")).toBeVisible()
    expect(screen.queryByTitle(/2026/)).not.toBeInTheDocument()
  })
  it("shows packaged origin without requiring protected system ownership", () => {
    render(<RecordProvenance record={{ system_installed: true, system_managed: false, created_by: "installer" }} />)
    expect(screen.getByRole("img", { name: "System installed" })).toBeVisible()
    expect(screen.queryByText("installer")).not.toBeInTheDocument()
    expect(adminExportValue("record_provenance", { system_installed: true })).toBe("System")
  })
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
