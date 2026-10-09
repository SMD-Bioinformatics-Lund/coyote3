import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { notifyActionError } from "@/lib/notifications"
import { QueryConditionTestPanel } from "./QueryConditionTestPanel"
import type { QueryCondition } from "./query-condition-types"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn() }))
const condition: QueryCondition = { type: "predicate", field: "size", operator: "gte", value: 10 }
beforeEach(() => vi.resetAllMocks())
function mount() {
  return render(<QueryClientProvider client={new QueryClient()}><QueryConditionTestPanel analysis="cnv" conditions={[{ id: "synthetic", condition }]} /></QueryClientProvider>)
}

it("tests only the supplied examples on explicit request and clears stale results", async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: { matches: [true, false], predicate: { size: { $gte: 10 } } } })
  mount()
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText("Test condition with synthetic examples"))
  fireEvent.change(screen.getByLabelText("Synthetic documents"), { target: { value: '[{"size": 12}, {"size": 2}]' } })
  fireEvent.click(screen.getByRole("button", { name: "Test condition" }))
  await screen.findByText("Does not match")
  expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/test-condition", { analysis: "cnv", condition, documents: [{ size: 12 }, { size: 2 }] })
  fireEvent.change(screen.getByLabelText("Synthetic documents"), { target: { value: '[{"size": 1}]' } })
  expect(screen.queryByText("Does not match")).not.toBeInTheDocument()
})

it("rejects invalid JSON examples before making a request", async () => {
  mount()
  fireEvent.click(screen.getByText("Test condition with synthetic examples"))
  fireEvent.change(screen.getByLabelText("Synthetic documents"), { target: { value: "{}" } })
  fireEvent.click(screen.getByRole("button", { name: "Test condition" }))
  await waitFor(() => expect(notifyActionError).toHaveBeenCalled())
  expect(api.post).not.toHaveBeenCalled()
})

it("keeps a valid test selection when the selected exception is removed", async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: { matches: [true], predicate: {} } })
  const client = new QueryClient()
  const rows = [{ id: "first", condition }, { id: "second", condition: { ...condition, value: 20 } }]
  const tree = (items: typeof rows) => <QueryClientProvider client={client}><QueryConditionTestPanel analysis="cnv" conditions={items} /></QueryClientProvider>
  const mounted = render(tree(rows))
  fireEvent.click(screen.getByText("Test condition with synthetic examples"))
  fireEvent.change(screen.getByLabelText("Exception"), { target: { value: "1" } })
  mounted.rerender(tree(rows.slice(0, 1)))
  expect(screen.getByLabelText("Exception")).toHaveValue("0")
  expect(screen.getByRole("button", { name: "Test condition" })).toBeEnabled()
  fireEvent.click(screen.getByRole("button", { name: "Test condition" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/test-condition", { analysis: "cnv", condition, documents: [{}] }))
})

it("hides a previous result while retrying and after a failed retry", async () => {
  let rejectRetry: (error: Error) => void = () => undefined
  vi.mocked(api.post).mockResolvedValueOnce({ status: 200, data: { matches: [true], predicate: {} } })
    .mockImplementationOnce(() => new Promise((_, reject) => { rejectRetry = reject }))
  mount()
  fireEvent.click(screen.getByText("Test condition with synthetic examples"))
  fireEvent.click(screen.getByRole("button", { name: "Test condition" }))
  await screen.findByText("Matches")
  fireEvent.click(screen.getByRole("button", { name: "Test condition" }))
  await waitFor(() => expect(screen.queryByText("Matches")).not.toBeInTheDocument())
  rejectRetry(new Error("Synthetic test failure"))
  await waitFor(() => expect(notifyActionError).toHaveBeenCalled())
  expect(screen.queryByText("Matches")).not.toBeInTheDocument()
})
