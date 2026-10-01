import { render, screen } from "@testing-library/react"
import { Outlet, useParams } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("./lib/runtime-paths", () => ({ APP_BASENAME: "" }))
vi.mock("./components/layout/Layout", () => ({ Layout: () => <main data-testid="layout"><Outlet /></main> }))
vi.mock("./components/layout/AppLoader", () => ({ AppLoader: () => <div role="status">Loading route</div> }))
vi.mock("./components/notifications/notification-store", () => ({ notify: vi.fn() }))
vi.mock("./components/admin/AdminPermissionBoundary", () => ({
  AdminPermissionBoundary: ({ permission, children }: { permission: string; children: React.ReactNode }) => (
    <div data-testid="permission-boundary" data-permission={permission}>{children}</div>
  ),
}))
vi.mock("./pages/auth/Login", () => ({ Login: () => <div>Login page</div> }))
vi.mock("./pages/admin/assays/AssaysPage", () => ({ AssaysPage: () => <div>Assays list</div> }))
vi.mock("./pages/admin/assays/AssayEditorPage", () => ({ AssayEditorPage: ({ mode }: { mode: string }) => <div>Assays {mode}</div> }))
vi.mock("./pages/admin/assay-configurations/AssayConfigurationsPage", () => ({ AssayConfigurationsPage: () => <div>Assay Configurations list</div> }))
vi.mock("./pages/admin/assay-configurations/AssayConfigurationEditorPage", () => ({ AssayConfigurationEditorPage: ({ mode }: { mode: string }) => <div>Assay Configurations {mode}</div> }))
vi.mock("./pages/admin/gene-lists/GeneListsPage", () => ({ GeneListsPage: () => <div>Gene Lists list</div> }))
vi.mock("./pages/admin/gene-lists/GeneListEditorPage", () => ({ GeneListEditorPage: ({ mode }: { mode: string }) => <div>Gene Lists {mode}</div> }))
vi.mock("./pages/admin/users/UsersPage", () => ({ UsersPage: () => <div>Users list</div> }))
vi.mock("./pages/admin/users/UserEditorPage", () => ({ UserEditorPage: ({ mode }: { mode: string }) => <div>Users {mode}</div> }))
vi.mock("./pages/admin/roles/RolesPage", () => ({ RolesPage: () => <div>Roles list</div> }))
vi.mock("./pages/admin/roles/RoleEditorPage", () => ({ RoleEditorPage: ({ mode }: { mode: string }) => <div>Roles {mode}</div> }))
vi.mock("./pages/admin/permissions/PermissionsPage", () => ({ PermissionsPage: () => <div>Permission Policies list</div> }))
vi.mock("./pages/admin/permissions/PermissionEditorPage", () => ({ PermissionEditorPage: ({ mode }: { mode: string }) => <div>Permission Policies {mode}</div> }))
vi.mock("./pages/admin/samples/AdminSamplesPage", () => ({ AdminSamplesPage: () => <div>Admin Samples list</div> }))
vi.mock("./pages/admin/samples/AdminSampleEditorPage", () => ({ AdminSampleEditorPage: ({ mode }: { mode: string }) => <div>Admin Samples {mode}</div> }))
vi.mock("./pages/Dashboard", () => ({ Dashboard: () => <div>Dashboard page</div> }))
vi.mock("./pages/KnowledgebaseDetails", () => ({ KnowledgebaseDetails: () => <div>Knowledgebase details page</div> }))
vi.mock("./pages/SampleDetail", () => ({ SampleDetail: () => {
  const { id } = useParams()
  return <div>Sample detail {id}</div>
} }))
vi.mock("./pages/admin/AdminAuditPage", () => ({ AdminAuditPage: () => <div>Audit page</div> }))
vi.mock("./pages/admin/AdminControlsPage", () => ({ AdminControlsPage: () => <div>Controls page</div> }))
vi.mock("./pages/admin/AdminIngestPage", () => ({ AdminIngestPage: () => <div>Ingest page</div> }))
vi.mock("./pages/static/AboutPage", () => ({
  AboutPage: () => <div>About page</div>,
}))
vi.mock("./pages/static/ContactPage", () => ({
  ContactPage: () => <div>Contact page</div>,
}))
vi.mock("./pages/static/NotFoundPage", () => ({
  NotFoundPage: () => <div>Not found page</div>,
}))

import App from "./App"
import { ADMIN_UTILITY_PERMISSIONS } from "./lib/access-control"

function navigate(path: string) {
  window.history.replaceState({}, "", path)
  return render(<App />)
}

describe("App route wiring", () => {
  beforeEach(() => window.history.replaceState({}, "", "/"))

  describe.each([
    ["asp", "Assays"],
    ["aspc", "Assay Configurations"],
    ["genelists", "Gene Lists"],
    ["users", "Users"],
    ["roles", "Roles"],
    ["permissions", "Permission Policies"],
    ["samples", "Admin Samples"],
  ])("%s resource routes", (resource, title) => {
    it.each(["list", "view", "edit"])("opens its own %s page", async (mode) => {
      navigate(`/admin/${resource}${mode === "list" ? "" : `/record/${mode}`}`)
      expect(await screen.findByText(`${title} ${mode}`)).toBeVisible()
    })
  })

  it("renders login outside the authenticated layout", () => {
    navigate("/login")
    expect(screen.getByText("Login page")).toBeVisible()
    expect(screen.queryByTestId("layout")).not.toBeInTheDocument()
  })

  it("renders lazy clinical routes inside the shared layout", async () => {
    navigate("/samples/SAMPLE_42")
    expect(await screen.findByText("Sample detail SAMPLE_42")).toBeVisible()
    expect(screen.getByTestId("layout")).toBeVisible()
  })

  it("routes the knowledgebase module to its details page", async () => {
    navigate("/knowledgebases")
    expect(await screen.findByText("Knowledgebase details page")).toBeVisible()
  })

  it("wraps protected admin routes in their exact permission boundary", async () => {
    navigate("/admin/audit")
    expect(await screen.findByText("Audit page")).toBeVisible()
    expect(screen.getByTestId("permission-boundary")).toHaveAttribute(
      "data-permission",
      ADMIN_UTILITY_PERMISSIONS.auditView,
    )
  })

  it.each(["/unknown/path", "/admin/unknown-resource", "/admin/unknown-resource/create", "/admin/unknown-resource/id/edit"])("uses the not-found route for %s", async (path) => {
    navigate(path)
    expect(await screen.findByText("Not found page")).toBeVisible()
    expect(screen.getByTestId("layout")).toBeVisible()
  })
})
