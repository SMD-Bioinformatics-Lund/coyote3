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
vi.mock("./pages/Dashboard", () => ({ Dashboard: () => <div>Dashboard page</div> }))
vi.mock("./pages/KnowledgebaseDetails", () => ({ KnowledgebaseDetails: () => <div>Knowledgebase details page</div> }))
vi.mock("./pages/SampleDetail", () => ({ SampleDetail: () => {
  const { id } = useParams()
  return <div>Sample detail {id}</div>
} }))
vi.mock("./pages/admin/AdminUtilityPages", () => ({
  AdminAuditPage: () => <div>Audit page</div>,
  AdminControlsPage: () => <div>Controls page</div>,
  AdminIngestPage: () => <div>Ingest page</div>,
  AdminSchemasPage: () => <div>Schemas page</div>,
}))
vi.mock("./pages/static/StaticPages", () => ({
  AboutPage: () => <div>About page</div>,
  ContactPage: () => <div>Contact page</div>,
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

  it("uses the not-found route for unknown authenticated paths", async () => {
    navigate("/unknown/path")
    expect(await screen.findByText("Not found page")).toBeVisible()
    expect(screen.getByTestId("layout")).toBeVisible()
  })
})
