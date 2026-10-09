import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import DemoInstallationPage from "./DemoInstallationPage"

const calls = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: calls }))

beforeEach(() => {
  vi.clearAllMocks()
  calls.get.mockResolvedValue({ data: {
    configuration: { assay_specific_panels: 9 }, configuration_installed: false,
    samples: [{ key: "demo_group_dna", name: "DEMO_GROUP_DNA", installed: false }],
  } })
  calls.post.mockResolvedValue({ data: { status: "installed" } })
})

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><DemoInstallationPage /></MemoryRouter></QueryClientProvider>)
}

it("requires acknowledgement and installs configuration before samples", async () => {
  show()
  const install = await screen.findByRole("button", { name: "Install configuration and samples" })
  expect(install).toBeDisabled()
  fireEvent.click(screen.getByRole("checkbox"))
  fireEvent.click(install)
  await waitFor(() => expect(calls.post).toHaveBeenCalledTimes(2))
  expect(calls.post.mock.calls.map((call) => call[0])).toEqual([
    "/admin/demo-installation/configuration", "/admin/demo-installation/samples/demo_group_dna",
  ])
})

it("stops on configuration failure and displays recovery status", async () => {
  calls.post.mockRejectedValue(new Error("Existing configuration conflicts"))
  show()
  await screen.findByRole("checkbox")
  fireEvent.click(screen.getByRole("checkbox"))
  fireEvent.click(screen.getByRole("button", { name: "Install configuration and samples" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Existing configuration conflicts")
  expect(calls.post).toHaveBeenCalledTimes(1)
  expect(screen.getByRole("status")).toHaveTextContent("Completed items are preserved")
})

it("does not reinstall existing samples or configuration", async () => {
  calls.get.mockResolvedValue({ data: { configuration: {}, configuration_installed: true,
    samples: [{ key: "demo_group_dna", name: "DEMO_GROUP_DNA", installed: true }] } })
  show()
  await screen.findByRole("checkbox")
  fireEvent.click(screen.getByRole("checkbox"))
  expect(screen.getByRole("button", { name: "Install configuration and samples" })).toBeDisabled()
  expect(calls.post).not.toHaveBeenCalled()
})
