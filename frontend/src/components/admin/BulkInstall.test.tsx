// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

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
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{kind === "assay-diagnoses" ? <BulkInstall kind={kind} aspId="panel-a" /> : <BulkInstall kind={kind} />}</QueryClientProvider>)
}
async function upload() {
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const file = new File([JSON.stringify(rows)], "diagnoses.json", { type: "application/json" })
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(rows) })
  fireEvent.change(screen.getByLabelText("Bulk upload diagnoses"), { target: { files: [file] } })
  await screen.findByRole("dialog")
}
beforeEach(() => { vi.clearAllMocks(); access.permissions = ["assay.panel:edit"]; vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} }) })
it("shows unresolved assay IDs on successfully imported diagnoses", async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 201, data: { meta: { unresolved_asp_ids: ["future-panel"] } } })
  mount()
  await upload()
  fireEvent.click(screen.getByRole("button", { name: "Install records" }))
  expect(await screen.findByText("1. first: Created · Unresolved assay IDs: future-panel")).toBeInTheDocument()
})
it("reviews a single ASPC upload before creating it through the normal API", async () => {
  access.permissions = ["assay.config:create"]
  const record = { asp_id: "synthetic", diagnosis_id: "base", environment: "production" }
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { form: { fields:
    Object.fromEntries(Object.keys(record).map(key => [key, { data_type: "str", required: true }])),
  } } })
  mount("aspc")
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const file = new File([JSON.stringify(record)], "aspc-base-production.json")
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(record) })
  fireEvent.change(screen.getByLabelText("Bulk upload aspc"), { target: { files: [file] } })
  const install = await screen.findByRole("button", { name: "Install records" })
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(install)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/aspc", { config: record }))
  expect(api.post).toHaveBeenCalledTimes(1)
})
it("imports association records into the selected assay through its normal create API", async () => {
  mount("assay-diagnoses")
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const file = new File([JSON.stringify(rows)], "associations.json")
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(rows) })
  fireEvent.change(screen.getByLabelText("Bulk upload assay-diagnoses"), { target: { files: [file] } })
  fireEvent.click(await screen.findByRole("button", { name: "Install records" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/asp/panel-a/diagnoses", rows[1]))
})
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
  fireEvent.change(screen.getByLabelText("Bulk records"), { target: { value: "- diagnosis_id: example\n  display_name: Example\n  unexpected: true" } })
  expect(screen.getByRole("status")).toHaveTextContent("unsupported keys: unexpected")
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

it("reviews gene lists from multiple files together and blocks duplicate IDs across files", async () => {
  access.permissions = ["gene_list.insilico:create"]
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { form: { fields: {
    isgl_id: { data_type: "str", required: true },
  } } } })
  mount("genelists")
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const input = screen.getByLabelText("Bulk upload genelists")
  expect(input).toHaveAttribute("multiple")
  function file(name: string, content: unknown) {
    const text = JSON.stringify(content)
    const result = new File([text], name)
    Object.defineProperty(result, "text", { value: async () => text })
    return result
  }
  const first = file("one.json", { isgl_id: "one" })
  fireEvent.change(input, { target: { files: [first, file("duplicate.json", { isgl_id: "ONE" })] } })
  expect(await screen.findByRole("alert")).toHaveTextContent("duplicate.json: Row 1: duplicate isgl_id")
  expect(screen.queryByRole("dialog")).toBeNull()
  fireEvent.change(input, { target: { files: [first, file("more.json", [{ isgl_id: "two" }, { isgl_id: "three" }])] } })
  const install = await screen.findByRole("button", { name: "Install records" })
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(install)
  await screen.findByText("3. three: Created")
  expect(vi.mocked(api.post).mock.calls).toEqual(["one", "two", "three"].map(isgl_id => ["/resources/genelists", { config: { isgl_id } }]))
})

it("imports reporting rules under their exported scopes as separate drafts", async () => {
  access.permissions = ["clinical_rules:draft"]
  mount("reporting-rules")
  await waitFor(() => expect(screen.getByRole("button", { name: "Upload JSON / YAML" })).toBeEnabled())
  const documents = ["panel-a", "panel-b"].map(asp_id => ({
    scope: { asp_id, diagnosis_id: "base", language: "sv", analyte: "dna" }, name: asp_id, blocks: [],
  }))
  const files = documents.map(document => {
    const text = JSON.stringify(document)
    const file = new File([text], document.name + ".json")
    Object.defineProperty(file, "text", { value: async () => text })
    return file
  })
  fireEvent.change(screen.getByLabelText("Bulk upload reporting-rules"), { target: { files } })
  const confirm = await screen.findByRole("button", { name: "Import drafts" })
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(confirm)
  await screen.findByText("2. panel-b / base / sv: Draft created")
  expect(vi.mocked(api.post).mock.calls).toEqual(documents.map(document => [
    "/admin/clinical-rule-sets/imports", { document, scope: document.scope, name: document.name },
  ]))
})
