import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { editLease, editSessionOptions } from "@/test/edit-lease"
import { QueryRulesPage } from "./QueryRulesPage"

const access = vi.hoisted(() => ({ permissions: ["query_rules:view", "query_rules:draft", "query_rules:publish"], roles: [] }))
vi.mock("@/lib/access-control", async original => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))

const scope = { assay_group: "example", asp_id: null, diagnosis_id: null, analysis: "snv", intent: "somatic", modality: null, family: null, environment: null }
const rule = { _id: "version-one", name: "Example selection", reason: "Reviewed", scope, content: { evidence_mode: null, exceptions: null }, version: 1, revision: 2, status: "approved", created_by: "author" }
beforeEach(() => {
  vi.resetAllMocks()
  access.permissions = ["query_rules:view", "query_rules:draft", "query_rules:publish"]
  vi.mocked(api.get).mockImplementation(async path => ({ status: 200, data: path.endsWith("/options") ? { groups: [{ id: "example", name: "Example laboratory" }], assays: [{ id: "panel", group: "example", category: "dna", diagnoses: ["myeloid"] }] } : { items: [] } }))
  vi.mocked(api.post).mockImplementation(async (url) => ({ status: 200, data: url.startsWith("/editing/") ? editLease() : { evidence_mode: "paired", exceptions: [], lineage: [{ source: "default", version: null }] } }))
})

function mount(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<MemoryRouter><QueryClientProvider client={client}><QueryRulesPage /></QueryClientProvider></MemoryRouter>)
}

it("separates policy preview and authorized sample testing from the editor", async () => {
  access.permissions.push("query_rules:test")
  mount()
  const preview = screen.getByRole("complementary", { name: "Query policy preview" })
  expect(within(preview).getByRole("button", { name: "Preview effective policy" })).toBeDisabled()
  expect(screen.getByRole("separator", { name: "Resize query preview" })).toBeInTheDocument()
  expect(screen.queryByRole("region", { name: "Test with a sample" })).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Test rules" })).toHaveAttribute("href", "/admin/query-rules/testing")
  const filter = screen.getByLabelText("Filter query rules by workflow state")
  expect(within(filter).getAllByRole("option").map(option => option.textContent)).toEqual([
    "All workflow states", "Draft", "Approved", "Published", "Retired",
  ])
  await screen.findByText("No published overrides. Default policies apply.")
})

it("filters the compact rule list without discarding the selected draft", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/options") ? original(path, options) : {
    status: 200, data: { items: [
      { ...rule, status: "draft" },
      { ...rule, _id: "other", name: "Other selection", status: "published", scope: { ...scope, assay_group: null } },
    ] },
  })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: /Example selection/ }))
  fireEvent.change(screen.getByLabelText("Change or review reason"), { target: { value: "Keep this reason" } })
  fireEvent.change(screen.getByLabelText("Search query rules"), { target: { value: "Other" } })
  expect(within(screen.getByRole("navigation", { name: "Query rule sets" })).queryByRole("button", { name: /Example selection/ })).not.toBeInTheDocument()
  expect(screen.getByLabelText("Change or review reason")).toHaveValue("Keep this reason")
  fireEvent.change(screen.getByLabelText("Filter query rules by workflow state"), { target: { value: "draft" } })
  expect(screen.getByText("No versions match these filters.")).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Search query rules"), { target: { value: "" } })
  fireEvent.change(screen.getByLabelText("Filter query rules by assay group"), { target: { value: "example" } })
  expect(within(screen.getByRole("navigation", { name: "Query rule sets" })).getByRole("button", { name: /Example selection/ })).toHaveAttribute("aria-pressed", "true")
  fireEvent.click(screen.getByRole("button", { name: "Collapse query-rule list" }))
  expect(screen.queryByRole("navigation", { name: "Query rule sets" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Expand query-rule list" }))
  expect(screen.getByLabelText("Filter query rules by workflow state")).toHaveValue("draft")
  expect(screen.getByLabelText("Change or review reason")).toHaveValue("Keep this reason")
})

it("opens the condition editor from an inherited scope without copying conditions", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => {
    const response = await original(path, options)
    if (!path.endsWith("/options")) return response
    return { ...response, data: { ...(response.data as Record<string, unknown>), conditions: {
      fields: { snv: [{ path: "genes", label: "Genes", kind: "string_list", operators: ["in"], value_role: "gene", filter_references: [{ key: "snvlists", kind: "string_list", path: "sample.filters.somatic.snv.snvlists" }] }] },
      operators: { in: "In" }, bson_types: [], max_depth: 6, max_nodes: 60, max_list_values: 100,
    } } }
  })
  mount()
  await within(screen.getByLabelText("Assay group")).findByRole("option", { name: "Example laboratory" })
  fireEvent.change(screen.getByLabelText("Assay group"), { target: { value: "example" } })
  fireEvent.click(screen.getByRole("button", { name: "Conditions (0)" }))
  fireEvent.click(screen.getByRole("button", { name: "Add condition" }))
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  expect(screen.getByLabelText("Exception list")).toHaveValue("extend")
  expect(screen.getByText("Parent rules · read-only")).toBeInTheDocument()
  expect(screen.getByLabelText("Value source")).toHaveValue("reference")
  fireEvent.click(screen.getByRole("button", { name: "Preview effective policy" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/preview", {
    scope, content: { evidence_mode: null, exception_mode: "extend", exceptions: [{ id: "", mode: "exclude", condition: { type: "predicate", field: "genes", operator: "in", value: { source: "sample.filters", key: "snvlists" } } }] },
  }))
})

it("offers related scopes and clears a diagnosis when returning to all assays", async () => {
  mount()
  await within(screen.getByLabelText("Assay group")).findByRole("option", { name: "Example laboratory" })
  fireEvent.change(screen.getByLabelText("Assay group"), { target: { value: "example" } })
  expect(within(screen.getByLabelText("Assay")).getByRole("option", { name: "panel" })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Assay"), { target: { value: "panel" } })
  fireEvent.change(screen.getByLabelText("Diagnosis"), { target: { value: "myeloid" } })
  fireEvent.change(screen.getByLabelText("Assay"), { target: { value: "" } })
  expect(screen.getByLabelText("Diagnosis")).toHaveValue("")
  expect(screen.getByLabelText("Diagnosis")).toBeEnabled()
})

it("authors a diagnosis and family policy for one environment without selecting an assay", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => {
    const response = await original(path, options)
    return path.endsWith("/options") ? { ...response, data: {
      groups: [{ id: "example", name: "Example laboratory" }],
      assays: [{ id: "panel", group: "example", category: "dna", family: "panel-dna", diagnoses: ["myeloid"] }],
      families: [{ id: "panel-dna", modality: "dna" }, { id: "panel-rna", modality: "rna" }],
      environments: ["production", "validation"],
    } } : response
  })
  mount()
  await within(screen.getByLabelText("Assay group")).findByRole("option", { name: "Example laboratory" })
  fireEvent.change(screen.getByLabelText("Assay group"), { target: { value: "example" } })
  fireEvent.change(screen.getByLabelText("Family"), { target: { value: "panel-dna" } })
  fireEvent.change(screen.getByLabelText("Diagnosis"), { target: { value: "myeloid" } })
  fireEvent.change(screen.getByLabelText("Environment"), { target: { value: "validation" } })
  expect(within(screen.getByLabelText("Family")).queryByRole("option", { name: "PANEL-RNA" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Preview effective policy" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/preview", {
    scope: { ...scope, diagnosis_id: "myeloid", modality: "dna", family: "panel-dna", environment: "validation" },
  }))
})

it("shows only authored conditions for a published version", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/options") ? original(path, options) : {
    status: 200, data: { items: [{ ...rule, status: "published", content: { evidence_mode: "paired", exceptions: [{ id: "cebpa", mode: "admit", condition: { type: "all", children: [
      { type: "predicate", field: "INFO.selected_CSQ.SYMBOL", operator: "in", value: ["CEBPA"] },
      { type: "predicate", field: "FILTER", operator: "in", value: ["GERMLINE"] },
    ] } }] } }] },
  })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: /Example selection/ }))
  const definition = screen.getByRole("region", { name: "Saved query definition" })
  fireEvent.click(screen.getByRole("button", { name: "Conditions (1)" }))
  expect(within(definition).getByText('"CEBPA"')).toBeVisible()
  expect(definition).toHaveTextContent('"CEBPA"')
  expect(definition).toHaveTextContent('"GERMLINE"')
  expect(within(definition).queryByRole("combobox")).not.toBeInTheDocument()
  expect(screen.queryByText("Search stored field names")).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Add condition" })).not.toBeInTheDocument()
  expect(screen.queryByText("Value guidance")).not.toBeInTheDocument()
})

it("requires confirmation before discarding local conditions for inheritance", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/options") ? original(path, options) : {
    status: 200, data: { items: [{ ...rule, status: "draft", content: { evidence_mode: null, exceptions: [{ id: "keep-me", mode: "exclude", genes: ["TP53"] }] } }] },
  })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: /Example selection/ }))
  fireEvent.change(await screen.findByLabelText("Exception list"), { target: { value: "inherit" } })
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancel" }))
  expect(screen.getByLabelText("Identifier")).toHaveValue("keep-me")
  expect(screen.getByLabelText("Exception list")).toHaveValue("replace")
  fireEvent.change(screen.getByLabelText("Exception list"), { target: { value: "inherit" } })
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }))
  expect(screen.queryByLabelText("Identifier")).not.toBeInTheDocument()
  expect(screen.getByLabelText("Exception list")).toHaveValue("inherit")
})

it("deletes only a selected draft after a reason and confirmation", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/options") ? original(path, options) : { status: 200, data: { items: [{ ...rule, status: "draft" }] } })
  vi.mocked(api.delete).mockResolvedValue({ status: 200, data: {} })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: /Example selection/ }))
  expect(screen.getByRole("button", { name: "Delete version" })).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Change or review reason"), { target: { value: "Unused" } })
  await waitFor(() => expect(screen.queryByText("Opening editing session…")).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole("button", { name: "Delete version" }))
  expect(api.delete).not.toHaveBeenCalled()
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }))
  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/admin/query-rule-sets/version-one", { ...editSessionOptions, body: JSON.stringify({ expected_revision: 2, reason: "Unused" }) }))
})

it("previews inherited fields separately from explicit empty exceptions", async () => {
  mount()
  await within(screen.getByLabelText("Assay group")).findByRole("option", { name: "Example laboratory" })
  fireEvent.change(screen.getByLabelText("Assay group"), { target: { value: "example" } })
  fireEvent.change(screen.getByLabelText("Assay"), { target: { value: "panel" } })
  fireEvent.change(screen.getByLabelText("Diagnosis"), { target: { value: "myeloid" } })
  fireEvent.change(screen.getByLabelText("Exception list"), { target: { value: "replace" } })
  fireEvent.click(screen.getByRole("button", { name: "Preview effective policy" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/preview", { scope: { ...scope, asp_id: "panel", diagnosis_id: "myeloid" }, content: { evidence_mode: null, exceptions: [], exception_mode: "replace" } }))
  expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/preview", { scope: { ...scope, asp_id: "panel", diagnosis_id: "myeloid" } })
  expect(api.put).not.toHaveBeenCalled()
})

it("requires confirmation and the inspected revision when publishing", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(["sample-variants", "SYNTHETIC"], { variants: [] })
  client.setQueryData(["report-preview", "SYNTHETIC"], { html: "Reviewed preview" })
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/options") ? original(path, options) : { status: 200, data: { items: [rule] } })
  vi.mocked(api.post).mockImplementation(async path => ({ status: 200, data: path.endsWith("/preview") ? { evidence_mode: "paired", exceptions: [], lineage: [] } : { ...rule, status: "published", revision: 3 } }))
  mount(client)
  fireEvent.click(await screen.findByRole("button", { name: /Example selection/ }))
  expect(screen.getByRole("region", { name: "Saved query definition" })).toHaveTextContent("example__all__base__somatic_snvs")
  expect(screen.queryByLabelText("Query ID")).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Change or review reason"), { target: { value: "Validation complete" } })
  fireEvent.click(screen.getByRole("button", { name: "Publish" }))
  expect(vi.mocked(api.post).mock.calls.some(([path]) => path.endsWith("/publish"))).toBe(false)
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/version-one/publish", { expected_revision: 2, reason: "Validation complete" }, {}))
  await waitFor(() => expect(client.getQueryState(["sample-variants", "SYNTHETIC"])?.isInvalidated).toBe(true))
  expect(client.getQueryState(["report-preview", "SYNTHETIC"])?.isInvalidated).toBe(true)
})

it("does not expose saving to a viewer", async () => {
  access.permissions = ["query_rules:view"]
  mount()
  await screen.findByText("No published overrides. Default policies apply.")
  expect(screen.getByRole("button", { name: "New scope version" })).toBeDisabled()
  expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument()
})

it("previews the global default without inventing a group or assay", async () => {
  mount()
  await within(screen.getByLabelText("Assay group")).findByRole("option", { name: "Example laboratory" })
  fireEvent.change(screen.getByLabelText("Assay group"), { target: { value: "__all_groups__" } })
  expect(screen.getByLabelText("Assay")).toBeDisabled()
  fireEvent.click(screen.getByRole("button", { name: "Preview effective policy" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/query-rule-sets/preview", { scope: { ...scope, assay_group: null } }))
})
