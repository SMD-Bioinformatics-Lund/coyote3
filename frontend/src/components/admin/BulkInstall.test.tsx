import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, expect, it, vi } from "vitest"
import { BulkInstall } from "./BulkInstall"
import { api, ApiClientError } from "@/lib/api"
import type { BulkKind } from "./bulk-import"

const access = vi.hoisted(() => ({ permissions: ["assay.panel:edit"] }))
vi.mock("@/lib/access-control", () => ({ useCurrentUserAccess: () => ({ data: access }), hasPermission: (_user: unknown, permission: string) => access.permissions.includes(permission) }))
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), api: { get: vi.fn(), post: vi.fn() } }))
const rows = [{ diagnosis_id: "first", display_name: "First" }, { diagnosis_id: "second", display_name: "Second" }]
function mount(kind: BulkKind = "diagnoses") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkInstall kind={kind} /></QueryClientProvider>)
}
async function upload() {
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const file = new File([JSON.stringify(rows)], "diagnoses.json", { type: "application/json" })
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(rows) })
  fireEvent.change(screen.getByLabelText("Bulk upload diagnoses"), { target: { files: [file] } })
  await screen.findByRole("dialog")
}
beforeEach(() => { vi.clearAllMocks(); access.permissions = ["assay.panel:edit"]; vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} }) })
it("hides uploading without the resource permission", () => {
  access.permissions = []; mount()
  expect(screen.queryByRole("button", { name: "Upload JSON / YAML" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Paste JSON / YAML" })).not.toBeInTheDocument()
})
it("validates pasted JSON live and requires review before installation", async () => {
  mount()
  await waitFor(() => expect(screen.getByRole("button", { name: "Paste JSON / YAML" })).toBeEnabled())
  fireEvent.click(screen.getByRole("button", { name: "Paste JSON / YAML" }))
  const editor = screen.getByLabelText("Bulk records")
  fireEvent.change(editor, { target: { value: '[{"diagnosis_id":' } })
  expect(editor).toHaveAttribute("aria-invalid", "true")
  expect(screen.getByRole("button", { name: "Review records" })).toBeDisabled()
  fireEvent.change(editor, { target: { value: JSON.stringify(rows) } })
  expect(editor).toHaveAttribute("aria-invalid", "false")
  expect(screen.getByRole("status")).toHaveTextContent("2 records ready to review")
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Review records" }))
  fireEvent.click(screen.getByRole("button", { name: "Edit pasted records" }))
  expect(screen.getByLabelText("Bulk records")).toHaveValue(JSON.stringify(rows))
  fireEvent.click(screen.getByRole("button", { name: "Review records" }))
  fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  await screen.findByText("2. second: Created")
})
it("validates YAML syntax and unsupported fields while editing an example", async () => {
  mount()
  await waitFor(() => expect(screen.getByRole("button", { name: "Show example" })).toBeEnabled())
  fireEvent.click(screen.getByRole("button", { name: "Show example" }))
  fireEvent.click(screen.getByRole("button", { name: "Edit example" }))
  expect((screen.getByLabelText("Bulk records") as HTMLTextAreaElement).value).toContain('"diagnosis_id"')
  fireEvent.change(screen.getByLabelText("Content format"), { target: { value: "yaml" } })
  fireEvent.change(screen.getByLabelText("Bulk records"), { target: { value: "- diagnosis_id: [" } })
  expect(screen.getByRole("status")).toHaveTextContent("Invalid YAML")
  fireEvent.change(screen.getByLabelText("Bulk records"), { target: { value: "- diagnosis_id: example\n  display_name: Example\n  created_by: system" } })
  expect(screen.getByRole("status")).toHaveTextContent("unsupported keys: created_by")
  expect(screen.getByRole("button", { name: "Review records" })).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Bulk records"), { target: { value: "- diagnosis_id: example\n  display_name: Example" } })
  expect(screen.getByRole("button", { name: "Review records" })).toBeEnabled()
  expect(api.post).not.toHaveBeenCalled()
})
it("shows a floating example with accepted keys without writing", async () => {
  mount()
  await waitFor(() => expect(screen.getByRole("button", { name: "Show example" })).toBeEnabled())
  fireEvent.click(screen.getByRole("button", { name: "Show example" }))
  expect(await screen.findByRole("dialog")).toHaveTextContent('"diagnosis_id"')
  expect(screen.getByRole("dialog")).toHaveTextContent("Accepted top-level keys")
  expect(api.post).not.toHaveBeenCalled()
})
it("requires review, posts individual records, and prevents accidental repeated installation", async () => {
  mount(); await upload()
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  await screen.findByText("2. second: Created")
  expect(api.post).toHaveBeenNthCalledWith(1, "/resources/diagnoses", rows[0])
  expect(api.post).toHaveBeenNthCalledWith(2, "/resources/diagnoses", rows[1])
  expect(screen.getByRole("button", { name: "Install records" })).toBeDisabled()
})
it("reports a duplicate without replacing it and continues with other records", async () => {
  vi.mocked(api.post).mockRejectedValueOnce(new ApiClientError("Already exists", 409))
  mount(); await upload(); fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  await screen.findByText("2. second: Created")
  expect(screen.getByText("1. first: Already exists")).toBeVisible()
})
it("stops after permission denial and marks remaining records unattempted", async () => {
  vi.mocked(api.post).mockRejectedValueOnce(new ApiClientError("Permission denied", 403))
  mount(); await upload(); fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  await screen.findByText("2. second: Not attempted")
  expect(api.post).toHaveBeenCalledTimes(1)
})
it("uses server form fields for gene lists and the existing config request envelope", async () => {
  access.permissions = ["gene_list.insilico:create"]
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { form: { fields: {
    isgl_id: { data_type: "str", required: true },
    name: { data_type: "str", required: true },
    genes: { data_type: "list", default: [] },
    created_by: { readonly: true, default: "operator" },
  } } } })
  mount("genelists")
  await waitFor(() => expect(screen.getByRole("button", { name: "Show example" })).toBeEnabled())
  fireEvent.click(screen.getByRole("button", { name: "Show example" }))
  expect(screen.getByRole("dialog")).not.toHaveTextContent("created_by")
  fireEvent.click(screen.getByRole("button", { name: "Close" }))
  const record = { isgl_id: "example-list", name: "Example list", genes: ["TP53"] }
  const file = new File([], "lists.json")
  Object.defineProperty(file, "text", { value: async () => JSON.stringify([record]) })
  fireEvent.change(screen.getByLabelText("Bulk upload genelists"), { target: { files: [file] } })
  await screen.findByRole("button", { name: "Install records" })
  fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/genelists", { config: record }))
})
