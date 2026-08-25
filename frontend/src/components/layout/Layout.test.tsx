import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { Layout } from "./Layout"

const navigate = vi.fn()

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock("@/components/notifications/use-notifications", () => ({
  useNotifications: () => ({ unreadCount: 7 }),
}))

vi.mock("./theme-toggle", () => ({
  ThemeToggle: () => <button type="button">Toggle theme</button>,
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return { ...actual, useNavigate: () => navigate }
})

const currentUser = {
  username: "analyst",
  firstname: "Avery",
  role: "manager",
  roles: ["manager"],
  access_level: 50,
  permissions: ["assay.config:view"],
}

const catalog = {
  meta: {
    nav_groups: [
      { category: "dna", family: "panel", assay_group: "hematology" },
      { category: "dna", family: "wgs", assay_group: "tumwgs" },
      { category: "rna", family: "wts", assay_group: "fusion" },
    ],
  },
}

function renderLayout(initialEntry = "/samples") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="*" element={<div>Route content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockPrivateQueries(
  getNavigationCounts: () => Record<string, number> = () => ({
    "dna:panel:hematology": 12,
    "dna:wgs:tumwgs": 3,
    "rna:wts:fusion": 4,
  }),
) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/public/modules") return { data: { modules: {} } } as never
    if (url === "/auth/whoami") return { data: currentUser } as never
    if (url === "/public/assay-catalog/context") return { data: catalog } as never
    if (url === "/samples/navigation-counts") {
      return {
        data: {
          counts: getNavigationCounts(),
        },
      } as never
    }
    if (url === "/public/contact") {
      return {
        data: {
          codebase: {
            bug_report_url: "https://example.test/bug",
            feature_request_url: "https://example.test/feature",
            support_request_url: "https://example.test/support",
          },
        },
      } as never
    }
    throw new Error(`Unexpected URL: ${url}`)
  })
}

describe("Layout", () => {
  beforeEach(() => {
    navigate.mockReset()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.delete).mockReset()
    vi.stubGlobal("fetch", vi.fn())
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    )
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })))
  })

  it("renders authenticated navigation, administration, and unread notifications", async () => {
    mockPrivateQueries()
    renderLayout()

    expect(await screen.findByText("Avery")).toBeVisible()
    expect(screen.getByLabelText("Notifications")).toHaveTextContent("7")
    expect(screen.getByTitle("Workspace: Samples")).toBeVisible()
    expect(screen.getByTitle("Administration: Admin Settings")).toBeVisible()
    expect(screen.getByText("Route content")).toBeVisible()
  })

  it("opens the assay menu, displays counts, and applies a sample filter", async () => {
    mockPrivateQueries()
    renderLayout("/")

    const dnaButton = await screen.findByRole("button", { name: /dna/i })
    fireEvent.click(dnaButton)

    expect(await screen.findByText("Filter samples by assay family and assay group.")).toBeVisible()
    const hematology = screen.getByTitle("DNA / panel / hematology")
    expect(hematology).toHaveTextContent("12")
    fireEvent.click(hematology)

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith(
        "/samples?panel_type=dna&panel_tech=panel&assay_group=hematology",
      )
    })
  })

  it("refreshes assay counts when the application regains focus", async () => {
    let hematologyCount = 12
    mockPrivateQueries(() => ({
      "dna:panel:hematology": hematologyCount,
      "dna:wgs:tumwgs": 3,
      "rna:wts:fusion": 4,
    }))
    renderLayout("/")

    fireEvent.click(await screen.findByRole("button", { name: /dna/i }))
    const hematology = await screen.findByTitle("DNA / panel / hematology")
    expect(hematology).toHaveTextContent("12")

    focusManager.setFocused(false)
    hematologyCount = 19
    focusManager.setFocused(true)

    await waitFor(() => expect(hematology).toHaveTextContent("19"))
  })

  it("exposes profile and support links and logs the user out", async () => {
    mockPrivateQueries()
    vi.mocked(api.delete).mockResolvedValue({ data: {} } as never)
    renderLayout()

    fireEvent.click(await screen.findByRole("button", { name: /Avery/i }))
    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute("href", "/profile")
    expect(screen.getByRole("link", { name: "Report a Bug" })).toHaveAttribute(
      "href",
      "https://example.test/bug",
    )

    fireEvent.click(screen.getByRole("button", { name: "Logout" }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/auth/sessions/current"))
    expect(navigate).toHaveBeenCalledWith("/login")
  })

  it("shows only public navigation and a sign-in action for an anonymous public route", async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 401 } as Response)
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === "/public/modules") return { data: { modules: {} } } as never
      if (url === "/public/assay-catalog/context") return { data: catalog } as never
      if (url === "/public/contact") return { data: {} } as never
      throw new Error(`Unexpected URL: ${url}`)
    })

    renderLayout("/public/catalog")

    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login")
    const toggle = screen.getByRole("button", { name: "Expand sidebar" })
    expect(toggle).toBeVisible()
    expect(screen.getByTitle("Public: Catalog")).toBeVisible()
    expect(screen.queryByLabelText("Notifications")).not.toBeInTheDocument()
    expect(screen.queryByTitle("Workspace: Samples")).not.toBeInTheDocument()
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument()

    fireEvent.click(toggle)
    expect(screen.getByText("Public")).toBeVisible()
    expect(screen.queryByText("Guest")).not.toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalledWith("/samples/navigation-counts")
  })

  it("expands and collapses the sidebar without losing route content", async () => {
    mockPrivateQueries()
    renderLayout()

    const toggle = await screen.findByTitle("Expand sidebar")
    fireEvent.click(toggle)
    expect(screen.getByText("Workspace")).toBeVisible()
    expect(screen.getAllByText("Avery")).toHaveLength(2)
    expect(screen.getAllByText("manager")).toHaveLength(2)
    expect(screen.getByText("Route content")).toBeVisible()
  })

  it("offers a back-to-top action when page height exceeds the viewport by ten percent", async () => {
    mockPrivateQueries()
    renderLayout()
    await screen.findByText("Route content")

    const main = screen.getByRole("main")
    Object.defineProperties(main, {
      clientHeight: { configurable: true, value: 800 },
      scrollHeight: { configurable: true, value: 1200 },
      scrollTop: { configurable: true, writable: true, value: 0 },
    })
    const scrollTo = vi.fn()
    Object.defineProperty(main, "scrollTo", { configurable: true, value: scrollTo })

    fireEvent.scroll(main)
    const backToTop = await screen.findByRole("button", { name: "Back to top" })
    fireEvent.click(backToTop)

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" })
  })
})
