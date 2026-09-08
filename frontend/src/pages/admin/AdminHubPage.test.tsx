import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AdminHubPage } from "./AdminHubPage"

const state = vi.hoisted(() => ({ permissions: [] as string[], roles: [] as string[], loading: false, ingest: true }))
vi.mock("@/lib/access-control", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/access-control")>(),
  useCurrentUserAccess: () => ({ data: state, isLoading: state.loading }),
}))
vi.mock("@/lib/app-module-state", () => ({
  useApplicationModules: () => ({ data: {} }),
  moduleIsEnabled: () => state.ingest,
}))

describe("Admin navigation permissions", () => {
  beforeEach(() => { state.permissions = []; state.roles = []; state.loading = false; state.ingest = true })
  const show = () => render(<MemoryRouter><AdminHubPage /></MemoryRouter>)
  it("does not expose links without permission", () => {
    show()
    expect(screen.getByText("Administration access is not assigned")).toBeInTheDocument()
    expect(screen.queryAllByRole("link")).toHaveLength(0)
  })
  it("shows only permitted resources", () => {
    state.permissions = ["catalog:view"]
    show()
    expect(screen.getByRole("link", { name: /Public Assay Catalog/ })).toHaveAttribute("href", "/admin/assay-catalog")
    expect(screen.queryByRole("link", { name: /Clinical Report Rules/ })).not.toBeInTheDocument()
  })
  it("allows superusers but respects disabled modules", () => {
    state.roles = ["superuser"]; state.ingest = false
    show()
    expect(screen.getByRole("link", { name: /Clinical Report Rules/ })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Ingest Workspace/ })).not.toBeInTheDocument()
  })
  it("does not expose links while authorization is loading", () => {
    state.loading = true
    show()
    expect(screen.queryAllByRole("link")).toHaveLength(0)
  })
})
