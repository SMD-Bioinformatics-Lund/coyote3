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
    expect(screen.getByRole("status", { name: "Checking administration access" })).toBeVisible()
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
})
