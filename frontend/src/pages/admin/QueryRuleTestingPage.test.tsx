import { render, screen, fireEvent } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { QueryRuleTestingPage } from "./QueryRuleTestingPage"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))

it("opens the linked saved version and clears sample testing when deselected", async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { items: [{
    _id: "saved", name: "Example query", version: 1, revision: 2, status: "draft",
    scope: { assay_group: "example", asp_id: null, subpanel_id: null, analysis: "snv", intent: "somatic" },
    content: { exceptions: [], evidence_mode: null },
  }] } })
  render(<MemoryRouter initialEntries={["/admin/query-rules/testing?version=saved"]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><QueryRuleTestingPage /></QueryClientProvider></MemoryRouter>)
  expect(await screen.findByRole("region", { name: "Test with a sample" })).toBeInTheDocument()
  expect(screen.getByLabelText("Rule-set version")).toHaveValue("saved")
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText("Rule-set version"), { target: { value: "" } })
  expect(screen.queryByRole("region", { name: "Test with a sample" })).not.toBeInTheDocument()
})
