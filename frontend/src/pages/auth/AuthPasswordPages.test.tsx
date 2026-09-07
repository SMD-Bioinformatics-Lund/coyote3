import { fireEvent, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { renderWithRouter } from "@/test/render"
import { ForgotPassword, ResetPassword } from "./AuthPasswordPages"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))

describe("password recovery pages", () => {
  beforeEach(() => vi.clearAllMocks())

  it("submits a password reset request", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never)
    renderWithRouter(<ForgotPassword />, "/forgot-password")

    fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "coyote3.user" } })
    fireEvent.click(screen.getByRole("button", { name: "Request reset" }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/auth/password/reset/request", { username: "coyote3.user" },
    ))
    expect(await screen.findByText(/reset email has been sent/i)).toBeVisible()
  })

  it("shows a service error for a failed reset request", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("Account is locked"))
    renderWithRouter(<ForgotPassword />, "/forgot-password")
    fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "locked" } })
    fireEvent.click(screen.getByRole("button", { name: "Request reset" }))
    expect(await screen.findByText("Account is locked")).toBeVisible()
  })

  it("rejects mismatched passwords before calling the API", () => {
    renderWithRouter(<ResetPassword />, "/reset-password?token=TOKEN")
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "first" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "second" } })
    fireEvent.click(screen.getByRole("button", { name: "Save password" }))
    expect(screen.getByText("New password and confirmation do not match.")).toBeVisible()
    expect(api.post).not.toHaveBeenCalled()
  })

  it("uses a URL token and confirms a matching password", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never)
    renderWithRouter(<ResetPassword />, "/reset-password?token=TOKEN")
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-secret" } })
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "new-secret" } })
    fireEvent.click(screen.getByRole("button", { name: "Save password" }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/auth/password/reset/confirm", { token: "TOKEN", new_password: "new-secret" },
    ))
    expect(await screen.findByText(/Password updated/)).toBeVisible()
  })
})
