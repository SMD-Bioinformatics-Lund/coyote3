import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const useCurrentUserAccess = vi.hoisted(() => vi.fn())
const hasPermission = vi.hoisted(() => vi.fn())

vi.mock("@/lib/access-control", () => ({ useCurrentUserAccess, hasPermission }))

import { AdminPermissionBoundary } from "./AdminPermissionBoundary"

describe("AdminPermissionBoundary", () => {
  beforeEach(() => {
    useCurrentUserAccess.mockReset()
    hasPermission.mockReset()
  })

  it("shows a loading state while access is unresolved", () => {
    useCurrentUserAccess.mockReturnValue({ isLoading: true })
    render(<AdminPermissionBoundary permission="user:view">Secret</AdminPermissionBoundary>)
    expect(screen.getByRole("status", { name: "Loading administration" })).toBeVisible()
    expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    expect(screen.queryByText("Secret")).not.toBeInTheDocument()
    expect(hasPermission).not.toHaveBeenCalled()
  })

  it("shows the required permission when access is denied", () => {
    useCurrentUserAccess.mockReturnValue({ isLoading: false, data: { permissions: [] } })
    hasPermission.mockReturnValue(false)
    render(<AdminPermissionBoundary permission="user:view">Secret</AdminPermissionBoundary>)
    expect(screen.getByText("Access not assigned")).toBeVisible()
    expect(screen.getByText("user:view")).toBeVisible()
    expect(screen.queryByText("Secret")).not.toBeInTheDocument()
  })

  it("renders protected content when permission is granted", () => {
    useCurrentUserAccess.mockReturnValue({ isLoading: false, data: { permissions: ["user:view"] } })
    hasPermission.mockReturnValue(true)
    render(<AdminPermissionBoundary permission="user:view">Secret</AdminPermissionBoundary>)
    expect(screen.getByText("Secret")).toBeVisible()
  })

  it("does not mount a clinical page when its permission is missing", () => {
    const loadClinicalData = vi.fn()
    function ClinicalPage() {
      loadClinicalData()
      return <div>Clinical results</div>
    }
    useCurrentUserAccess.mockReturnValue({ isLoading: false, data: { roles: ["sys_admin"] } })
    hasPermission.mockReturnValue(false)
    render(
      <AdminPermissionBoundary area="Clinical" permission="sample:view">
        <ClinicalPage />
      </AdminPermissionBoundary>,
    )
    expect(screen.getByText("Your roles do not grant access to this clinical workflow.")).toBeVisible()
    expect(loadClinicalData).not.toHaveBeenCalled()
  })
})
