import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  access: {
    data: {
      username: "admin",
      roles: ["superuser"],
      role: "superuser",
      access_level: 100,
      permissions: [] as string[],
    } as any,
    isLoading: false,
  },
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api: { get: mocks.get, post: mocks.post, put: mocks.put, patch: mocks.patch, delete: mocks.delete },
}))
vi.mock("@/lib/access-control", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/access-control")>()
  return { ...actual, useCurrentUserAccess: () => mocks.access }
})
vi.mock("@/lib/notifications", () => ({
  notifySuccess: mocks.success,
  notifyActionError: mocks.error,
}))

import { AdminResourceEditorPage, AdminResourcePage } from "./AdminResourcePages"
import { adminCell } from "./resource-list"

function renderResource(resource: string, children?: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/${resource}`]}>
        <Routes>
          <Route path="/admin/:resource" element={<AdminResourcePage />} />
          <Route path="*" element={children || <div>Destination</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function renderEditor(resource: string, mode: "create" | "edit" | "view", id = "") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const path = mode === "create" ? `/admin/${resource}/create` : `/admin/${resource}/${id}/${mode}`
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/:resource/create" element={<AdminResourceEditorPage mode="create" />} />
          <Route path="/admin/:resource/:id/edit" element={<AdminResourceEditorPage mode="edit" />} />
          <Route path="/admin/:resource/:id/view" element={<AdminResourceEditorPage mode="view" />} />
          <Route path="/admin/:resource" element={<div>Resource list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("AdminResourcePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.access.isLoading = false
    mocks.access.data = {
      username: "admin",
      roles: ["superuser"],
      role: "superuser",
      access_level: 100,
      permissions: [],
    }
    mocks.get.mockResolvedValue({ data: {} })
    mocks.post.mockResolvedValue({ data: {} })
    mocks.put.mockResolvedValue({ data: {} })
    mocks.patch.mockResolvedValue({ data: {} })
    mocks.delete.mockResolvedValue({ data: {} })
  })

  it("blocks resource loading when the current user lacks list permission", async () => {
    mocks.access.data = {
      username: "viewer",
      roles: ["viewer"],
      role: "viewer",
      access_level: 10,
      permissions: [],
    }
    renderResource("users")

    expect(await screen.findByText("You do not have permission to list users.")).toBeVisible()
    expect(mocks.get).not.toHaveBeenCalled()
    expect(screen.queryByRole("link", { name: "Create" })).not.toBeInTheDocument()
  })

  it("loads users and filters them by role, authentication type, and status", async () => {
    mocks.get.mockResolvedValue({
      data: {
        users: [
          { username: "local.admin", roles: ["admin"], auth_type: ["local"], is_active: true },
          { username: "ldap.viewer", roles: ["viewer"], auth_type: ["ldap"], is_active: false },
        ],
      },
    })
    const user = userEvent.setup()
    renderResource("users")

    expect(await screen.findByText("local.admin")).toBeVisible()
    expect(screen.getByText("ldap.viewer")).toBeVisible()
    await user.selectOptions(screen.getByLabelText("Role"), "admin")
    expect(screen.getByText("local.admin")).toBeVisible()
    expect(screen.queryByText("ldap.viewer")).not.toBeInTheDocument()
    expect(screen.getByText("1 of 2 loaded")).toBeVisible()

    await user.selectOptions(screen.getByLabelText("Authentication"), "local")
    await user.selectOptions(screen.getByLabelText("Status"), "true")
    expect(screen.getByText("local.admin")).toBeVisible()
  })

  it("uses server filter options and sends assay filters for admin samples", async () => {
    mocks.get.mockImplementation(() => Promise.resolve({
      data: {
        samples: [{ name: "CASE_001", asp_group: "hematology", asp_id: "hema_gmsv1", ingest_status: "ready" }],
        filter_options: { asp_group: ["hematology"], asp_id: ["hema_gmsv1"] },
      },
    }))
    const user = userEvent.setup()
    renderResource("samples")

    expect(await screen.findByText("CASE_001")).toBeVisible()
    await user.selectOptions(screen.getByLabelText("Assay group"), "hematology")
    await waitFor(() => expect(mocks.get).toHaveBeenLastCalledWith(expect.stringContaining("asp_group=hematology")))
    await user.selectOptions(screen.getByLabelText("Assay"), "hema_gmsv1")
    await waitFor(() => expect(mocks.get).toHaveBeenLastCalledWith(expect.stringContaining("asp_id=hema_gmsv1")))
  })

  it("groups permission policies and limits system permissions to view and status actions", async () => {
    mocks.get.mockResolvedValue({
      data: {
        permission_policies: [
          { permission_id: "sample:view", label: "View samples", category: "Samples", system_managed: true, is_active: true },
          { permission_id: "custom:review", label: "Custom review", category: "Clinical", system_managed: false, is_active: true },
        ],
      },
    })
    renderResource("permissions")

    expect(await screen.findByRole("heading", { name: "Permission Categories" })).toBeVisible()
    expect(screen.getByRole("link", { name: "sample:view" })).toHaveAttribute("href", "/admin/permissions/sample%3Aview/view")
    expect(screen.getByRole("link", { name: "custom:review" })).toHaveAttribute("href", "/admin/permissions/custom%3Areview/edit")
    const systemRow = screen.getByTitle("sample:view").closest("tr")
    expect(systemRow).not.toBeNull()
    expect(within(systemRow as HTMLElement).getByTitle(/Its definition cannot be edited or deleted/)).toBeVisible()
    expect(within(systemRow as HTMLElement).getByTitle("Toggle active")).toBeVisible()
    expect(within(systemRow as HTMLElement).queryByTitle("Edit")).not.toBeInTheDocument()
    expect(within(systemRow as HTMLElement).queryByTitle("Delete")).not.toBeInTheDocument()
  })

  it("allows a system role to be maintained but not deleted", async () => {
    mocks.get.mockResolvedValue({
      data: {
        roles: [{ role_id: "viewer", name: "Viewer", system_managed: true, is_active: true }],
      },
    })
    renderResource("roles")

    const row = (await screen.findByText("viewer")).closest("tr") as HTMLElement
    expect(within(row).getByTitle("Edit")).toBeVisible()
    expect(within(row).getByTitle("Toggle active")).toBeVisible()
    expect(within(row).queryByTitle("Delete")).not.toBeInTheDocument()
    expect(within(row).getByTitle(/This record can be edited or deactivated/)).toBeVisible()
  })

  it("requires confirmation before deleting a resource and reports success", async () => {
    mocks.get.mockResolvedValue({ data: { roles: [{ role_id: "reviewer", name: "Reviewer", is_active: true }] } })
    mocks.delete.mockResolvedValue({ data: { resource_name: "Reviewer", resource_id: "reviewer" } })
    const user = userEvent.setup()
    renderResource("roles")

    const row = (await screen.findByText("reviewer")).closest("tr") as HTMLElement
    await user.click(within(row).getByTitle("Delete"))
    expect(screen.getByRole("heading", { name: "Confirm delete" })).toBeVisible()
    expect(mocks.delete).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "Confirm" }))
    await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith("/roles/reviewer"))
    expect(mocks.success).toHaveBeenCalledWith(
      "Roles deleted",
      "Reviewer was deleted.",
      "Admin roles",
      expect.objectContaining({ id: "reviewer", name: "Reviewer" }),
    )
  })

  it("shows API failures instead of an empty table", async () => {
    mocks.get.mockRejectedValue(new Error("Users service unavailable"))
    renderResource("users")
    expect(await screen.findByText("Users service unavailable")).toBeVisible()
  })

  it("builds a create payload from typed, grouped, conditional, and structured fields", async () => {
    mocks.get.mockResolvedValue({
      data: {
        form: {
          sections: {
            identity: ["username", "password", "access_level", "score", "is_active", "provider"],
            assignment: ["analysis_types", "use_adhoc", "list_types", "notes", "metadata", "filters"],
          },
          fields: {
            username: { label: "Username", required: true },
            password: { label: "Password", display_type: "password" },
            access_level: { label: "Access level", data_type: "int" },
            score: { label: "Score", data_type: "float" },
            is_active: { label: "Active", display_type: "checkbox", default: true },
            provider: { label: "Provider", display_type: "select", options: [{ value: "local", label: "Local" }, { value: "ldap", label: "LDAP" }] },
            analysis_types: { label: "Analysis types", display_type: "checkbox-group", options: ["SNV", "CNV"] },
            use_adhoc: { label: "Ad hoc", display_type: "checkbox" },
            list_types: {
              label: "List types",
              display_type: "checkbox-group",
              conditional_options: { field: "use_adhoc", falsy: ["snv"], truthy: ["adhoc_snv"] },
            },
            notes: { label: "Notes", data_type: "list" },
            metadata: { label: "Metadata", data_type: "json", default: { threshold: 1 } },
            filters: {
              label: "Filters",
              display_type: "filters-structured",
              groups: [{ title: "SNV filters", requires_analysis: ["SNV"], fields: [{ key: "snv.min_depth", label: "Minimum depth", type: "int", default: 100 }] }],
            },
          },
        },
      },
    })
    const user = userEvent.setup()
    renderEditor("users", "create")

    await user.type(await screen.findByLabelText(/Username/), "reviewer")
    await user.type(screen.getByLabelText(/Password/), "synthetic-test-password")
    await user.type(screen.getByLabelText(/Access level/), "25")
    await user.type(screen.getByLabelText(/Score/), "1.5")
    await user.selectOptions(screen.getByLabelText(/Provider/), "ldap")
    await user.click(screen.getByLabelText("SNV"))
    const adhocField = screen.getByText("Ad hoc").closest("label")?.querySelector("input")
    expect(adhocField).not.toBeNull()
    await user.click(adhocField as HTMLInputElement)
    expect(screen.getByLabelText("adhoc_snv")).toBeVisible()
    expect(screen.queryByLabelText("snv")).not.toBeInTheDocument()
    await user.click(screen.getByLabelText("adhoc_snv"))
    fireEvent.change(screen.getByLabelText(/Notes/), { target: { value: "first\nsecond" } })
    await user.clear(screen.getByDisplayValue("1"))
    await user.type(screen.getByPlaceholderText("Value"), "42")
    await user.clear(screen.getByLabelText(/Minimum depth/))
    await user.type(screen.getByLabelText(/Minimum depth/), "250")
    await user.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/users", {
      form_data: expect.objectContaining({
        username: "reviewer",
        password: "synthetic-test-password",
        access_level: 25,
        score: 1.5,
        is_active: true,
        provider: "ldap",
        analysis_types: ["SNV"],
        use_adhoc: true,
        list_types: ["adhoc_snv"],
        notes: ["first", "second"],
        metadata: { threshold: 42 },
        filters: { snv: { min_depth: 250 } },
      }),
    }))
    expect(await screen.findByText("Resource list")).toBeVisible()
  })

  it("limits ASPC analysis types to the selected ASP category and sequencing family", async () => {
    mocks.get.mockResolvedValue({
      data: {
        form: {
          sections: { identity: ["asp_id", "subpanel_id", "analysis_types"] },
          fields: {
            asp_id: {
              label: "ASP",
              display_type: "select",
              options: [
                { value: "rna_panel", label: "RNA fusion panel" },
                { value: "wts_panel", label: "WTS panel" },
              ],
            },
            subpanel_id: {
              label: "Subpanel",
              display_type: "select",
              default: "base",
              options_by_field: {
                field: "asp_id",
                values: {
                  rna_panel: ["base", "heme"],
                  wts_panel: ["base", "myeloid"],
                },
              },
            },
            analysis_types: {
              label: "Analysis types",
              display_type: "checkbox-group",
              default: ["FUSION"],
              help: "Select an ASP to see the analysis types available for its sequencing family.",
              options_by_field: {
                field: "asp_id",
                values: {
                  rna_panel: ["FUSION", "QC", "PGX"],
                  wts_panel: ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"],
                },
              },
            },
          },
        },
      },
    })
    const user = userEvent.setup()
    renderEditor("aspc", "create")

    expect(await screen.findByText(/Select an ASP to see the analysis types/)).toBeVisible()
    await user.selectOptions(screen.getByRole("combobox", { name: "ASP" }), "rna_panel")
    expect(screen.getByRole("combobox", { name: "Subpanel" })).toHaveValue("base")
    await user.selectOptions(screen.getByRole("combobox", { name: "Subpanel" }), "heme")
    expect(screen.getByLabelText("FUSION")).toBeVisible()
    expect(screen.getByLabelText("QC")).toBeVisible()
    expect(screen.queryByLabelText("EXPRESSION")).not.toBeInTheDocument()

    await user.selectOptions(screen.getByRole("combobox", { name: "ASP" }), "wts_panel")
    expect(screen.getByRole("combobox", { name: "Subpanel" })).toHaveValue("")
    expect(screen.getByRole("option", { name: "myeloid" })).toBeVisible()
    expect(screen.getByLabelText("EXPRESSION")).toBeVisible()
    expect(screen.getByLabelText("CLASSIFICATION")).toBeVisible()
  })

  it("shows ASP-scoped optional gene-list checkboxes and clears stale selections", async () => {
    mocks.get.mockResolvedValue({
      data: {
        form: {
          sections: { identity: ["asp_id"], filters: ["filters"] },
          fields: {
            asp_id: {
              label: "ASP",
              display_type: "select",
              options: ["hema_gmsv1", "solid_gmsv3"],
            },
            filters: {
              label: "Filters",
              display_type: "filters-structured",
              groups: [
                {
                  title: "Somatic SNV scope",
                  fields: [
                    {
                      key: "somatic.snv.snvlists",
                      label: "SNV Gene Lists",
                      type: "checkbox-group",
                      options: [],
                      options_by_field: {
                        field: "asp_id",
                        values: {
                          hema_gmsv1: [{ value: "hema_snv", label: "Hematology SNV" }],
                          solid_gmsv3: [{ value: "solid_snv", label: "Solid SNV" }],
                        },
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
      },
    })
    const user = userEvent.setup()
    renderEditor("aspc", "create")

    await user.selectOptions(await screen.findByRole("combobox", { name: "ASP" }), "hema_gmsv1")
    const hematologyList = await screen.findByLabelText("Hematology SNV")
    expect(hematologyList).not.toBeChecked()
    await user.click(hematologyList)
    expect(hematologyList).toBeChecked()

    await user.selectOptions(screen.getByRole("combobox", { name: "ASP" }), "solid_gmsv3")
    expect(await screen.findByLabelText("Solid SNV")).not.toBeChecked()
    await waitFor(() => expect(screen.queryByLabelText("Hematology SNV")).not.toBeInTheDocument())
  })

  it("combines ASP choices for all selected genelist assay groups", async () => {
    mocks.get.mockResolvedValue({
      data: {
        form: {
          sections: { scope: ["asp_groups", "asp_ids"] },
          fields: {
            asp_groups: {
              label: "Assay groups",
              display_type: "checkbox-group",
              options: ["hematology", "solid"],
            },
            asp_ids: {
              label: "ASPs",
              display_type: "checkbox-group",
              help: "Select assay groups first.",
              options_by_field: {
                field: "asp_groups",
                values: {
                  hematology: [{ value: "hema_gmsv1", label: "Hematology GMSv1" }],
                  solid: [{ value: "solid_gmsv3", label: "Solid DNA GMSv3" }],
                },
              },
            },
          },
        },
      },
    })
    const user = userEvent.setup()
    renderEditor("genelists", "create")

    expect((await screen.findAllByText("Select assay groups first."))[0]).toBeVisible()
    await user.click(screen.getByLabelText("hematology"))
    expect(screen.getByLabelText("Hematology GMSv1")).toBeVisible()
    expect(screen.queryByLabelText("Solid DNA GMSv3")).not.toBeInTheDocument()

    await user.click(screen.getByLabelText("solid"))
    expect(screen.getByLabelText("Hematology GMSv1")).toBeVisible()
    expect(screen.getByLabelText("Solid DNA GMSv3")).toBeVisible()

    await user.click(screen.getByLabelText("Hematology GMSv1"))
    await user.click(screen.getByLabelText("hematology"))
    expect(screen.queryByLabelText("Hematology GMSv1")).not.toBeInTheDocument()
  })

  it("omits blank passwords and readonly fields from edit payloads", async () => {
    mocks.get.mockResolvedValue({ data: {
      user_doc: { username: "reviewer", email: "old@example.org", immutable_id: "SYS-1" },
      form: { fields: {
        username: { label: "Username", readonly: true },
        email: { label: "Email" },
        password: { label: "Password", display_type: "password" },
        immutable_id: { label: "Immutable ID", readonly_mode: ["edit"] },
      } },
    } })
    const user = userEvent.setup()
    renderEditor("users", "edit", "reviewer")

    const email = await screen.findByLabelText(/Email/)
    await user.clear(email)
    await user.type(email, "new@example.org")
    await user.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(mocks.put).toHaveBeenCalledWith("/users/reviewer", {
      form_data: { email: "new@example.org" },
    }))
  })

  it("imports a configuration JSON file into a create form without saving it", async () => {
    mocks.get.mockResolvedValue({ data: {
      form: { fields: {
        asp_id: { label: "ASP ID", required: true },
        display_name: { label: "Display name", required: true },
        is_active: { label: "Active", display_type: "checkbox", default: true },
      } },
    } })
    renderEditor("asp", "create")

    await screen.findByLabelText(/ASP ID/)
    const file = new File([JSON.stringify({ asp_id: "new_assay", display_name: "New assay", is_active: false })], "assay.json", {
      type: "application/json",
    })
    fireEvent.change(screen.getByLabelText("Import configuration JSON"), { target: { files: [file] } })

    await waitFor(() => expect(screen.getByLabelText(/ASP ID/)).toHaveValue("new_assay"))
    expect(screen.getByLabelText(/Display name/)).toHaveValue("New assay")
    expect(screen.getByLabelText(/Active/)).not.toBeChecked()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it("uses the imported ASPC category before filling the create form", async () => {
    mocks.get.mockImplementation((path: string) => Promise.resolve({ data: {
      form: { fields: {
        asp_category: { label: "Category", readonly: true },
        asp_id: { label: "ASP ID", required: true },
        environment: { label: "Environment", required: true },
      } },
      requested_path: path,
    } }))
    renderEditor("aspc", "create")

    await screen.findByLabelText(/ASP ID/)
    const file = new File([JSON.stringify({ asp_category: "RNA", asp_id: "fusion", environment: "testing" })], "rna-aspc.json", {
      type: "application/json",
    })
    fireEvent.change(screen.getByLabelText("Import configuration JSON"), { target: { files: [file] } })

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith("/resources/aspc/create_context?category=RNA"))
    await waitFor(() => expect(screen.getByLabelText(/ASP ID/)).toHaveValue("fusion"))
    expect(screen.getByLabelText(/Environment/)).toHaveValue("testing")
  })

  it("uses a color picker and persists the selected role badge color", async () => {
    mocks.get.mockResolvedValue({ data: {
      role: { role_id: "reviewer", color: "#64748b" },
      form: { fields: {
        role_id: { label: "Role ID", readonly: true },
        color: { label: "Color", display_type: "color", required: true },
      } },
    } })
    renderEditor("roles", "edit", "reviewer")

    fireEvent.change(await screen.findByLabelText("Color picker"), { target: { value: "#dc2626" } })
    expect(screen.getByLabelText("Color hex value")).toHaveValue("#dc2626")
    await userEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(mocks.put).toHaveBeenCalledWith("/roles/reviewer", {
      form_data: { color: "#dc2626" },
    }))
  })

  it("renders view mode read-only and forces system permissions out of edit mode", async () => {
    mocks.get.mockResolvedValue({ data: {
      permission: { permission_id: "sample:view", label: "View samples", system_managed: true },
      form: { fields: {
        permission_id: { label: "Permission ID" },
        label: { label: "Label" },
        system_managed: { label: "System managed", display_type: "checkbox" },
      } },
    } })
    renderEditor("permissions", "edit", "sample:view")

    expect((await screen.findAllByRole("heading", { name: "View Permission Policies" })).length).toBe(2)
    expect(screen.getByLabelText(/Permission ID/)).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()
  })

  it("shows editor save failures without navigating away", async () => {
    mocks.get.mockResolvedValue({ data: { form: { fields: { role_id: { label: "Role ID" } } } } })
    mocks.post.mockRejectedValue(new Error("Role validation failed"))
    const user = userEvent.setup()
    renderEditor("roles", "create")

    await user.type(await screen.findByLabelText(/Role ID/), "reviewer")
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(await screen.findByText("Role validation failed")).toBeVisible()
    expect(mocks.error).toHaveBeenCalled()
    expect(screen.queryByText("Resource list")).not.toBeInTheDocument()
  })

  it("edits sample documents as JSON and blocks invalid syntax", async () => {
    const sample = {
      _id: "507f191e810c19729de860ea",
      name: "SYNTHETIC_001",
      asp_id: "assay_1",
      environment: "production",
    }
    mocks.get.mockResolvedValue({ data: { sample } })
    const user = userEvent.setup()
    renderEditor("samples", "edit", "507f191e810c19729de860ea")

    const editor = await screen.findByRole("textbox", { name: "Sample JSON" })
    expect(screen.getByText("Valid JSON object")).toBeVisible()
    expect(screen.getByRole("button", { name: "Save sample" })).toBeDisabled()

    fireEvent.change(editor, { target: { value: '{\n  "name": "SYNTHETIC_001",\n}' } })
    expect(screen.queryByText("Valid JSON object")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save sample" })).toBeDisabled()

    const editedSample = { ...sample, environment: "testing" }
    fireEvent.change(editor, { target: { value: JSON.stringify(editedSample) } })
    expect(screen.getByText("Valid JSON object")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Save sample" }))

    await waitFor(() => expect(mocks.put).toHaveBeenCalledWith(
      "/resources/samples/507f191e810c19729de860ea",
      { sample: editedSample },
    ))
  })

  it("renders the sample JSON document read-only in view mode", async () => {
    mocks.get.mockResolvedValue({ data: { sample: { _id: "sample-id", name: "SYNTHETIC_001" } } })
    renderEditor("samples", "view", "sample-id")

    expect(await screen.findByRole("textbox", { name: "Sample JSON" })).toHaveAttribute("readonly")
    expect(screen.queryByRole("button", { name: "Save sample" })).not.toBeInTheDocument()
  })
})

describe("admin resource table typography", () => {
  it("emphasizes only the primary identifier among ordinary scalar values", () => {
    const { rerender } = render(adminCell("aspc_id", { aspc_id: "hema_gmsv1_base_production" }, { primaryIdentifier: true }))

    expect(screen.getByText("hema_gmsv1_base_production")).toHaveClass("font-semibold")

    rerender(adminCell("asp_id", { asp_id: "hema_gmsv1" }))
    expect(screen.getByText("hema_gmsv1")).toHaveClass("font-normal")
    expect(screen.getByText("hema_gmsv1")).not.toHaveClass("font-semibold")
  })
})
