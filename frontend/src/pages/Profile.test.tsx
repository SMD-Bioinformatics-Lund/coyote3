import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), success: vi.fn(), error: vi.fn(),
}))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post, patch: mocks.patch } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: mocks.success, notifyActionError: mocks.error }))

import { Profile } from "./Profile"

function mount(user: Record<string, unknown>) {
  mocks.get.mockResolvedValue({ data: { user } })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><MemoryRouter><Profile /></MemoryRouter></QueryClientProvider>,
  )
}

describe("Profile", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows identity, access scope, roles, and effective permissions", async () => {
    mount({
      username: "coyote3.user", fullname: "Coyote User", firstname: "Coyote", lastname: "User",
      email: "user@example.org", job_title: "Scientist", role: "user", roles: ["user", "viewer"],
      auth_type: ["local", "ldap"], environments: ["production"], asp_ids: ["hema_gmsv1"],
      asp_groups: ["hematology"], permissions: ["sample:view", "variant:comment:add"],
    })

    expect(await screen.findByRole("heading", { name: "Coyote User" })).toBeVisible()
    expect(screen.getByRole("link", { name: /user@example.org/ })).toHaveAttribute("href", "mailto:user@example.org")
    expect(screen.getByText("production")).toBeVisible()
    expect(screen.getByText("hema_gmsv1")).toBeVisible()
    expect(screen.getByText("sample:view")).toBeVisible()
  })

  it("updates only editable profile fields", async () => {
    mocks.patch.mockResolvedValue({ data: { ok: true } })
    mount({ username: "coyote3.user", firstname: "Old", auth_type: ["local"] })
    const firstName = await screen.findByLabelText("First name")
    fireEvent.change(firstName, { target: { value: "New" } })
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }))

    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith("/auth/profile", {
      firstname: "New", lastname: "", fullname: "", job_title: "",
    }))
    expect(mocks.success).toHaveBeenCalledWith("Profile updated", expect.any(String), "Profile")
  })

  it("changes a local password and clears the form", async () => {
    mocks.post.mockResolvedValue({ data: { ok: true } })
    mount({ username: "local.user", auth_type: ["local"] })
    const current = await screen.findByLabelText("Current password")
    const next = screen.getByLabelText("New password")
    fireEvent.change(current, { target: { value: "old" } })
    fireEvent.change(next, { target: { value: "new" } })
    fireEvent.click(screen.getByRole("button", { name: "Update password" }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith(
      "/auth/password/change", { current_password: "old", new_password: "new" },
    ))
    expect(await screen.findByText("Password changed.")).toBeVisible()
    expect(current).toHaveValue("")
    expect(next).toHaveValue("")
  })

  it("disables local password controls for LDAP-only accounts", async () => {
    mount({ username: "ldap.user", auth_type: ["ldap"] })
    expect(await screen.findByText(/LDAP-only accounts/)).toBeVisible()
    expect(screen.getByLabelText("Current password")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Update password" })).toBeDisabled()
  })
})
