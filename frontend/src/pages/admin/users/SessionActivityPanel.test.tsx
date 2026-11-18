// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { SessionActivityPanel } from "./SessionActivityPanel"

const access = vi.hoisted(() => ({
  data: { username: "synthetic-admin", roles: ["superuser"], permissions: ["user:list"] },
}))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }))
vi.mock("@/lib/access-control", async importOriginal => ({
  ...await importOriginal<typeof import("@/lib/access-control")>(),
  useCurrentUserAccess: () => access,
}))

const summary = {
  signed_in_users: 2, active_sessions: 3, recently_active_users: 1,
  recent_activity_seconds: 300, observed_at: "2026-11-18T12:00:00Z",
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><SessionActivityPanel /></QueryClientProvider>)
}

describe("Superuser login activity", () => {
  beforeEach(() => {
    access.data.roles = ["superuser"]
    vi.mocked(api.get).mockReset()
  })

  it("shows distinct users separately from sessions and refreshes their counts", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: summary } as never)
    const user = userEvent.setup()
    renderPanel()
    const panel = screen.getByRole("region", { name: "Login activity" })
    expect(await within(panel).findByText("2")).toBeVisible()
    expect(within(panel).getByText("3")).toBeVisible()
    expect(within(panel).getByText("1")).toBeVisible()
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ...summary, signed_in_users: 4 } } as never)
    await user.click(within(panel).getByRole("button", { name: "Refresh" }))
    expect(await within(panel).findByText("4")).toBeVisible()
    expect(within(panel).queryByText("2")).not.toBeInTheDocument()
  })

  it("does not request or display counts for a regular user administrator", () => {
    access.data.roles = ["sys_admin"]
    renderPanel()
    expect(screen.queryByRole("region", { name: "Login activity" })).not.toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalled()
  })

  it("hides stale counts after a failed refresh and allows recovery", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: summary } as never)
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText("2")
    vi.mocked(api.get).mockRejectedValueOnce(new Error("Unavailable"))
    await user.click(screen.getByRole("button", { name: "Refresh" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Login activity is unavailable")
    expect(screen.queryByText("2")).not.toBeInTheDocument()
    vi.mocked(api.get).mockResolvedValueOnce({ data: { ...summary, signed_in_users: 0, active_sessions: 0, recently_active_users: 0 } } as never)
    await user.click(screen.getByRole("button", { name: "Refresh" }))
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument())
    expect(screen.getAllByText("0")).toHaveLength(3)
  })
})
