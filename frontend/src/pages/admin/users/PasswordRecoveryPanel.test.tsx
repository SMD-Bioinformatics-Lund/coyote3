// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { PasswordRecoveryPanel } from "./PasswordRecoveryPanel"

const access = vi.hoisted(() => ({ data: { username: "admin", roles: ["sys_admin"], permissions: ["user:edit"] } }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock("@/lib/access-control", async importOriginal => ({
  ...await importOriginal<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => access,
}))
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PasswordRecoveryPanel /></QueryClientProvider>)
}
beforeEach(() => {
  vi.resetAllMocks()
  access.data.roles = ["sys_admin"]
  vi.mocked(api.get).mockResolvedValue({ data: [{ request_id: "r1", username: "synthetic", provider: "ldap", status: "pending", requested_at: "2026-11-18T10:00:00Z" }] } as never)
})
it("requires confirmation and submits no password when completing a request", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: {} } as never)
  show()
  fireEvent.click(await screen.findByRole("button", { name: "Mark completed" }))
  expect(api.post).not.toHaveBeenCalled()
  expect(screen.getByRole("alertdialog")).toBeVisible()
  fireEvent.click(screen.getAllByRole("button", { name: "Mark completed" }).at(-1)!)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/users/password-recovery/r1/complete", {}, { errorNotice: "inline" }))
  await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
})
it("does not fetch account recovery for a clinical administrator", () => {
  access.data.roles = ["admin"]
  show()
  expect(api.get).not.toHaveBeenCalled()
  expect(screen.queryByText("Password recovery")).not.toBeInTheDocument()
})
it("retains confirmation for a failed completion so the administrator can retry", async () => {
  vi.mocked(api.post).mockRejectedValue(new Error("Unavailable"))
  show()
  fireEvent.click(await screen.findByRole("button", { name: "Mark completed" }))
  fireEvent.click(screen.getAllByRole("button", { name: "Mark completed" }).at(-1)!)
  expect(await screen.findByText(/Unable to record completion/)).toBeVisible()
  expect(screen.getByRole("alertdialog")).toBeVisible()
})
