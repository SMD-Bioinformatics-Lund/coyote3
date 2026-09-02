import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { CommentsPanel } from "./CommentsPanel"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn(), notifySuccess: vi.fn() }))
const accessState = vi.hoisted(() => ({
  permissions: [
    "sample.comment:hide",
    "sample.comment:unhide",
    "variant.comment:hide",
    "variant.comment:unhide",
  ],
}))
vi.mock("@/lib/access-control", () => ({
  useCurrentUserAccess: () => ({ data: { roles: [], permissions: accessState.permissions } }),
  hasPermission: (user: { permissions?: string[] } | undefined, permission: string) => Boolean(user?.permissions?.includes(permission)),
}))

function renderPanel(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

describe("CommentsPanel", () => {
  beforeEach(() => {
    accessState.permissions = [
      "sample.comment:hide",
      "sample.comment:unhide",
      "variant.comment:hide",
      "variant.comment:unhide",
    ]
    vi.mocked(api.post).mockReset().mockResolvedValue({ data: {} } as never)
    vi.mocked(api.patch).mockReset().mockResolvedValue({ data: {} } as never)
    vi.mocked(api.delete).mockReset().mockResolvedValue({ data: {} } as never)
  })

  it("loads an existing comment into the editor and supports markdown tools", async () => {
    const user = userEvent.setup()
    const onUseAsDraft = vi.fn()
    renderPanel(<CommentsPanel sampleId="CASE_1" comments={[{ _id: "c1", author: "analyst", text: "Existing clinical note" }]} onUseAsDraft={onUseAsDraft} />)

    await user.click(screen.getByTitle("Load this comment into the editor"))
    expect(screen.getByRole("textbox")).toHaveValue("Existing clinical note")
    expect(onUseAsDraft).toHaveBeenCalledWith("Existing clinical note")

    await user.clear(screen.getByRole("textbox"))
    await user.click(screen.getByTitle("Bold"))
    expect(screen.getByRole("textbox")).toHaveValue("**bold text**")
  })

  it("uses suggested text and saves a sample comment", async () => {
    const user = userEvent.setup()
    renderPanel(<CommentsPanel sampleId="CASE_1" suggestedText="Suggested clinical summary" />)

    await user.click(screen.getByRole("button", { name: "Suggest" }))
    expect(screen.getByRole("textbox")).toHaveValue("Suggested clinical summary")
    expect(screen.getByText("Preview")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Save comment" }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/samples/CASE_1/comments", {
      form_data: { sample_comment: "Suggested clinical summary" },
    }))
    expect(screen.getByRole("textbox")).toHaveValue("")
  })

  it("escapes selected markdown syntax without changing the comment format", async () => {
    const user = userEvent.setup()
    renderPanel(<CommentsPanel sampleId="CASE_1" />)

    const textarea = screen.getByRole<HTMLTextAreaElement>("textbox")
    await user.type(textarea, "**Literal text**")
    textarea.focus()
    textarea.setSelectionRange(0, textarea.value.length)
    await user.click(screen.getByTitle("Escape Markdown"))
    expect(textarea).toHaveValue("\\*\\*Literal text\\*\\*")
    await user.click(screen.getByRole("button", { name: "Save comment" }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/samples/CASE_1/comments", {
      form_data: { sample_comment: "\\*\\*Literal text\\*\\*" },
    }))
  })

  it("serializes variant identity and global scope for finding annotations", async () => {
    const user = userEvent.setup()
    const resource = {
      _id: "variant-1",
      CHROM: "17",
      POS: 76736896,
      REF: "T",
      ALT: "C",
      INFO: { selected_CSQ: { SYMBOL: "SRSF2", Feature: "NM_003016.4", HGVSc: "c.265A>G", HGVSp: "p.Met89Val" } },
    }
    renderPanel(<CommentsPanel sampleId="CASE_1" resourceType="small_variant" resource={resource} assayGroup="hematology" subpanel="hem" />)

    await user.type(screen.getByRole("textbox"), "Reviewed annotation")
    await user.click(screen.getByRole("checkbox", { name: "Global annotation" }))
    await user.click(screen.getByRole("button", { name: "Save comment" }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/samples/CASE_1/annotations", {
      id: "variant-1",
      form_data: expect.objectContaining({
        text: "Reviewed annotation",
        global: "global",
        gene: "SRSF2",
        transcript: "NM_003016.4",
        nomenclature: "p",
        variant: "p.Met89Val",
        hgvsc: "c.265A>G",
        hgvsp: "p.Met89Val",
        genomic: "17_76736896_T_C",
        assay_group: "hematology",
        subpanel: "hem",
      }),
    }))
  })

  it("uses the correct hide and restore methods", async () => {
    const user = userEvent.setup()
    const view = renderPanel(<CommentsPanel sampleId="CASE_1" comments={[{ _id: "c1", text: "Visible note" }]} showComposer={false} />)
    await user.click(screen.getByRole("button", { name: "Hide" }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/samples/CASE_1/comments/c1/hidden", {}))

    view.rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CommentsPanel sampleId="CASE_1" comments={[{ _id: "c1", text: "Hidden note", hidden: true }]} showComposer={false} />
      </QueryClientProvider>,
    )
    await user.click(screen.getByRole("button", { name: "Show hidden (1)" }))
    await user.click(screen.getByRole("button", { name: "Unhide" }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/samples/CASE_1/comments/c1/hidden", {}))
  })

  it("keeps hidden comments inactive while preserving the explicit restore action", async () => {
    const user = userEvent.setup()
    const onUseAsDraft = vi.fn()
    renderPanel(
      <CommentsPanel
        sampleId="CASE_1"
        comments={[{ _id: "c1", text: "Hidden clinical note", hidden: true }]}
        onUseAsDraft={onUseAsDraft}
      />,
    )

    expect(screen.queryByText("Hidden clinical note")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Show hidden (1)" }))
    const hiddenComment = screen.getByRole("button", { name: "Hidden clinical note" })
    expect(hiddenComment).toBeDisabled()
    expect(hiddenComment).not.toHaveAttribute("title")

    await user.click(hiddenComment)
    expect(screen.getByRole("textbox")).toHaveValue("")
    expect(onUseAsDraft).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Unhide" }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/samples/CASE_1/comments/c1/hidden", {}))
  })

  it("does not expose hidden comments or their visibility control without both permissions", () => {
    accessState.permissions = ["sample.comment:hide"]
    renderPanel(
      <CommentsPanel
        sampleId="CASE_1"
        comments={[
          { _id: "visible", text: "Active comment" },
          { _id: "hidden", text: "Restricted hidden comment", hidden: true },
        ]}
        showComposer={false}
      />,
    )

    expect(screen.getByText("Active comment")).toBeInTheDocument()
    expect(screen.queryByText("Restricted hidden comment")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /show hidden/i })).not.toBeInTheDocument()
  })

  it("labels annotations authored for a different transcript", () => {
    const resource = {
      INFO: { selected_CSQ: { Feature: "NM_003016.4" } },
    }

    renderPanel(
      <CommentsPanel
        sampleId="CASE_1"
        resourceType="small_variant"
        resource={resource}
        comments={[
          { _id: "alternate", text: "Alternate transcript annotation", transcript: "NM_003016.3" },
          { _id: "selected", text: "Selected transcript annotation", transcript: "NM_003016.4" },
        ]}
        showComposer={false}
      />,
    )

    expect(screen.getByText("Transcript NM_003016.3")).toBeInTheDocument()
    expect(screen.queryByText("Transcript NM_003016.4")).not.toBeInTheDocument()
  })
})
