import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AdminHubPage } from "./AdminHubPage"

const state = vi.hoisted(() => ({ permissions: [] as string[], roles: [] as string[], loading: false, ingest: true, error: false, modulesError: false, retry: vi.fn() }))
vi.mock("@/lib/access-control", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/access-control")>(),
  useCurrentUserAccess: () => ({ data: state, isLoading: state.loading, isError: state.error, refetch: state.retry }),
}))
vi.mock("@/lib/app-module-state", () => ({
  useApplicationModules: () => ({ data: {}, isError: state.modulesError, refetch: state.retry }),
  moduleIsEnabled: () => state.ingest,
}))

describe("Admin navigation permissions", () => {
  beforeEach(() => { state.permissions = []; state.roles = []; state.loading = false; state.ingest = true; state.error = false; state.modulesError = false; state.retry.mockClear() })
  const show = () => render(<MemoryRouter><AdminHubPage /></MemoryRouter>)
  it("distinguishes failed authorization from missing permission", () => {
    state.error = true
    show()
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load administration access")
    expect(screen.queryByText("Administration access is not assigned")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(state.retry).toHaveBeenCalledOnce()
  })
  it("does not link ingest when module availability cannot be checked", () => {
    state.roles = ["superuser"]; state.modulesError = true
    show()
    expect(screen.queryByRole("link", { name: /Ingest Workspace/ })).not.toBeInTheDocument()
    expect(screen.getByRole("alert")).toHaveTextContent("Ingest availability")
  })
  it("filters authorized destinations by category and search and clears them", () => {
    state.roles = ["superuser"]
    show()
    fireEvent.click(screen.getByRole("tab", { name: "Reporting and catalog" }))
    expect(screen.getAllByRole("link")).toHaveLength(3)
    fireEvent.change(screen.getByRole("textbox", { name: "Search administration" }), { target: { value: " testing " } })
    expect(screen.getAllByRole("link")).toHaveLength(1)
    expect(screen.getByRole("link", { name: /Clinical Rule Testing/ })).toBeVisible()
    fireEvent.change(screen.getByRole("textbox", { name: "Search administration" }), { target: { value: "no match" } })
    expect(screen.queryAllByRole("link")).toHaveLength(0)
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))
    expect(screen.getAllByRole("link")).toHaveLength(19)
  })
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
  it("links assay viewers to subpanel administration", () => {
    state.permissions = ["assay.panel:list", "assay.panel:view"]
    show()
    expect(screen.getByRole("link", { name: /Subpanel definitions/ })).toHaveAttribute("href", "/admin/subpanels")
    expect(screen.getByRole("link", { name: /Assay subpanel associations/ })).toHaveAttribute("href", "/admin/assay-subpanels")
  })
  it("hides the subpanel card without assay-list access", () => {
    state.permissions = ["assay.panel:view"]
    show()
    expect(screen.queryByRole("link", { name: /Subpanel definitions/ })).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Assay subpanel associations/ })).not.toBeInTheDocument()
  })
  it("does not expose links while authorization is loading", () => {
    state.loading = true
    show()
    expect(screen.queryAllByRole("link")).toHaveLength(0)
  })
  it("groups every administrative destination once by responsibility", () => {
    state.roles = ["superuser"]
    show()
    const assays = screen.getByRole("region", { name: "Assays and subpanels" })
    expect(within(assays).getByRole("link", { name: /^Assay groups/ })).toBeInTheDocument()
    expect(within(assays).getByRole("link", { name: /^Subpanel definitions/ })).toBeInTheDocument()
    const reporting = screen.getByRole("region", { name: "Reporting and catalog" })
    expect(within(reporting).getByRole("link", { name: /^Clinical Report Rules/ })).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Identity and access" })).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Application operations" })).toBeInTheDocument()
    const destinations = screen.getAllByRole("link").map((link) => link.getAttribute("href"))
    expect(destinations).toHaveLength(19)
    expect(new Set(destinations).size).toBe(destinations.length)
  })
  it("omits empty sections for limited access", () => {
    state.permissions = ["catalog:view"]
    show()
    expect(screen.getAllByRole("region")).toHaveLength(1)
    expect(screen.getByRole("region", { name: "Reporting and catalog" })).toBeInTheDocument()
  })
})
