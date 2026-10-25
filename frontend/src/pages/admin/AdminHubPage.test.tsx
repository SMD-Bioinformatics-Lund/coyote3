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
  it("searches across all groups without category tabs and clears the search", () => {
    state.roles = ["superuser"]
    show()
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
    expect(screen.getAllByRole("link")).toHaveLength(22)
    fireEvent.change(screen.getByRole("textbox", { name: "Search administration" }), { target: { value: " testing " } })
    expect(screen.getAllByRole("link")).toHaveLength(2)
    expect(screen.getByRole("link", { name: /Clinical Rule Testing/ })).toBeVisible()
    expect(screen.getByRole("link", { name: /Query Rule Testing/ })).toBeVisible()
    fireEvent.change(screen.getByRole("textbox", { name: "Search administration" }), { target: { value: "no match" } })
    expect(screen.queryAllByRole("link")).toHaveLength(0)
    fireEvent.click(screen.getAllByRole("button", { name: "Clear search" })[1])
    expect(screen.getAllByRole("link")).toHaveLength(22)
  })
  it("does not expose links without permission", () => {
    show()
    expect(screen.getByText("Administration access is not assigned")).toBeInTheDocument()
    expect(screen.queryAllByRole("link")).toHaveLength(0)
  })
  it("shows only permitted resources", () => {
    state.permissions = ["catalog:view"]
    show()
    expect(screen.getByRole("link", { name: /Assay Catalog/ })).toHaveAttribute("href", "/admin/assay-catalog")
    expect(screen.queryByRole("link", { name: /Reporting Rule Sets/ })).not.toBeInTheDocument()
  })
  it("allows superusers but respects disabled modules", () => {
    state.roles = ["superuser"]; state.ingest = false
    show()
    expect(screen.getByRole("link", { name: /Reporting Rule Sets/ })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Ingest Workspace/ })).not.toBeInTheDocument()
  })
  it("links assay viewers to diagnosis administration", () => {
    state.permissions = ["assay.panel:list", "assay.panel:view"]
    show()
    expect(screen.getByRole("link", { name: /Diagnosis definitions/ })).toHaveAttribute("href", "/admin/diagnoses")
    expect(screen.getByRole("link", { name: /Assay diagnosis associations/ })).toHaveAttribute("href", "/admin/assay-diagnoses")
  })
  it("hides the diagnosis card without assay-list access", () => {
    state.permissions = ["assay.panel:view"]
    show()
    expect(screen.queryByRole("link", { name: /Diagnosis definitions/ })).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Assay diagnosis associations/ })).not.toBeInTheDocument()
  })
  it("does not expose links while authorization is loading", () => {
    state.loading = true
    show()
    expect(screen.queryAllByRole("link")).toHaveLength(0)
  })
  it("groups every administrative destination once by responsibility", () => {
    state.roles = ["superuser"]
    show()
    const assays = screen.getByRole("region", { name: "Assays and diagnoses" })
    expect(within(assays).getByRole("link", { name: /^Assay groups/ })).toBeInTheDocument()
    expect(within(assays).getByRole("link", { name: /^Diagnosis definitions/ })).toBeInTheDocument()
    const reporting = screen.getByRole("region", { name: "Clinical rules and catalog" })
    expect(within(reporting).getByRole("link", { name: /^Reporting Rule Sets/ })).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Identity and access" })).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Application operations" })).toBeInTheDocument()
    const destinations = screen.getAllByRole("link").map((link) => link.getAttribute("href"))
    expect(destinations).toHaveLength(22)
    expect(new Set(destinations).size).toBe(destinations.length)
  })
  it("omits empty sections for limited access", () => {
    state.permissions = ["catalog:view"]
    show()
    expect(screen.getAllByRole("region")).toHaveLength(1)
    expect(screen.getByRole("region", { name: "Clinical rules and catalog" })).toBeInTheDocument()
  })
  it("shows demo installation in operations with its dedicated permission", () => {
    state.permissions = ["demo:install"]
    show()
    const operations = screen.getByRole("region", { name: "Application operations" })
    expect(within(operations).getByRole("link", { name: /^Demo installation/ }))
      .toHaveAttribute("href", "/admin/demo-installation")
    expect(screen.getAllByRole("link")).toHaveLength(1)
  })
  it("hides demo installation from operators without its permission", () => {
    state.permissions = ["app.controls:view"]
    show()
    expect(screen.getByRole("link", { name: /^Application Controls/ })).toBeVisible()
    expect(screen.queryByRole("link", { name: /^Demo installation/ })).not.toBeInTheDocument()
  })
})
