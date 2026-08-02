import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))

import { moduleIsEnabled } from "./app-module-state"
import { ApplicationModuleBoundary } from "./app-modules"

function renderWithQuery(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>)
}

describe("application module controls", () => {
  beforeEach(() => vi.clearAllMocks())

  it("treats an absent module response as enabled so bootstrap failures do not hide the app", () => {
    expect(moduleIsEnabled(undefined, "reports")).toBe(true)
  })

  it("renders a governed route when the module is enabled", async () => {
    mocks.get.mockResolvedValue({
      data: { modules: { reports: { enabled: true, label: "Clinical reporting", description: "Reports" } } },
    })
    renderWithQuery(
      <ApplicationModuleBoundary moduleKey="reports">
        <div>Report route</div>
      </ApplicationModuleBoundary>,
    )
    expect(await screen.findByText("Report route")).toBeVisible()
  })

  it("renders an unavailable state instead of a disabled route", async () => {
    mocks.get.mockResolvedValue({
      data: {
        modules: {
          reports: {
            enabled: false,
            label: "Clinical reporting",
            description: "Report preview, rendering, saving, and report retrieval.",
          },
        },
      },
    })
    renderWithQuery(
      <ApplicationModuleBoundary moduleKey="reports">
        <div>Report route</div>
      </ApplicationModuleBoundary>,
    )
    expect(await screen.findByRole("heading", { name: "Clinical reporting is unavailable" })).toBeVisible()
    expect(screen.queryByText("Report route")).not.toBeInTheDocument()
    expect(screen.getByText(/API requests for it return HTTP 503/)).toBeVisible()
  })
})
