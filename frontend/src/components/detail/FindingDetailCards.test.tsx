import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ClassificationsCard, CommentsCard } from "./FindingDetailCards"
import { DetailCard } from "./FindingDetailLayout"

const { patch, notifySuccess } = vi.hoisted(() => ({ patch: vi.fn(), notifySuccess: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { patch } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess, notifyActionError: vi.fn() }))
vi.mock("@/lib/access-control", () => ({
  useCurrentUserAccess: () => ({ data: { permissions: ["tier:remove:global"] } }),
  hasPermission: (user: { permissions: string[] }, permission: string) => user.permissions.includes(permission),
}))
vi.mock("@/lib/app-module-state", () => ({
  useApplicationModules: () => ({
    data: {
      modules: {},
      curation: {
        tiering: {
          small_variant: true,
          cnv: false,
          fusion: true,
          translocation: false,
        },
      },
    },
  }),
  tieringIsEnabled: (payload: any, resourceType: string) =>
    payload.curation.tiering[resourceType],
}))

function renderWithQuery(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  vi.spyOn(client, "invalidateQueries")
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) }
}

describe("finding detail cards", () => {
  it("emphasizes the current tier and shows matching history with author, text and date", () => {
    renderWithQuery(<ClassificationsCard
      latest={{ class: 2, author: "current-reviewer", time_created: "2026-03-01T10:00:00Z", history: [
        { _id: "previous", class: 1, text: "Previous reasoning", author: "previous-reviewer", time_created: "2026-02-01T10:00:00Z", is_active: false },
        { _id: "oldest", class: 3, text: "Original reasoning", author: "first-reviewer", time_created: "2026-01-01T10:00:00Z" },
      ] }}
      sampleId="S1" resourceType="small_variant" resourceId="V1"
    />)
    expect(screen.getByRole("button", { name: "Tier 2" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("button", { name: "Tier 2" })).toHaveClass("opacity-100")
    expect(screen.getByRole("button", { name: "Tier 1" })).toHaveClass("opacity-65")
    const entries = within(screen.getByRole("region", { name: "Classification history" })).getAllByRole("article")
    expect(entries).toHaveLength(2)
    expect(entries[0]).toHaveTextContent("Previous reasoning")
    expect(entries[0]).toHaveTextContent("previous-reviewer")
    expect(entries[0]).toHaveTextContent("Inactive")
    expect(entries[0]).toHaveTextContent("2026")
    expect(entries[1]).toHaveTextContent("Original reasoning")
    expect(screen.getByText("current-reviewer")).toBeVisible()
  })
  it("distinguishes reference tiers from the effective classification", () => {
    renderWithQuery(<ClassificationsCard latest={{ class: 999 }} other={[
      { class: 2, asp_group: "solid", asp_id: "demo-solid", diagnosis_id: "lung", namespace: "clinical", effective: false, requires_retiering: true },
    ]} />)
    expect(screen.getByText("Not currently classified.")).toBeVisible()
    expect(screen.getByText("solid · demo-solid · lung · clinical")).toBeVisible()
    expect(screen.getByText(/Re-tier required/)).toBeVisible()
    expect(screen.queryByText("Latest classification")).not.toBeInTheDocument()
  })
  it("renders active comments and excludes hidden comments", () => {
    const { rerender } = renderWithQuery(<CommentsCard />)
    expect(screen.getByText("No comments available.")).toBeInTheDocument()
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <CommentsCard comments={[
          { _id: "1", author: "analyst", text: "Visible note", created_at: "2026-08-02T10:00:00Z" },
          { _id: "2", user: "reviewer", comment: "Hidden note", hidden: true },
        ]} />
      </QueryClientProvider>,
    )
    expect(screen.getByText("Visible note")).toBeInTheDocument()
    expect(screen.queryByText("Hidden note")).not.toBeInTheDocument()
  })

  it("renders a reusable card title and content", () => {
    const Icon = () => <svg aria-hidden="true" />
    renderWithQuery(<DetailCard title="Evidence" icon={Icon}>Evidence body</DetailCard>)
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeInTheDocument()
    expect(screen.getByText("Evidence body")).toBeInTheDocument()
  })

  it("confirms Tier III classification and invalidates finding data", async () => {
    patch.mockResolvedValueOnce({ ok: true })
    const onUpdate = vi.fn()
    const { client } = renderWithQuery(
      <ClassificationsCard
        latest={{ class: 2, reason: "Potential significance" }}
        other={[{ _id: "old", tier: 1, text: "Previous classification" }]}
        sampleId="S1"
        resourceType="small_variant"
        resourceId="V1"
        onUpdate={onUpdate}
      />,
    )
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "Tier 3" }))
    expect(screen.getByText("This will persist a Tier 3 classification for the finding.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Set classification" }))

    await waitFor(() => expect(patch).toHaveBeenCalledWith("/samples/S1/classifications/tier", {
      resource_type: "small_variant",
      resource_ids: ["V1"],
      tier: 3,
      apply: true,
    }))
    expect(onUpdate).toHaveBeenCalled()
    expect(client.invalidateQueries).toHaveBeenCalled()
    expect(notifySuccess).toHaveBeenCalledWith(
      "Classification updated",
      "Finding classified as Tier 3.",
      "Classification",
    )
  })

  it("confirms removal and hides mutation controls without a complete identity", async () => {
    patch.mockResolvedValueOnce({ ok: true })
    const user = userEvent.setup()
    const { rerender } = renderWithQuery(
      <ClassificationsCard latest={{ tier: 4 }} sampleId="S1" resourceType="small_variant" resourceId="V1" />,
    )
    await user.click(screen.getByRole("button", { name: "Deactivate" }))
    await user.click(screen.getByRole("button", { name: "Deactivate annotations" }))
    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      "/samples/S1/classifications/tier",
      expect.objectContaining({ tier: 4, apply: false }),
    ))

    rerender(<QueryClientProvider client={new QueryClient()}><ClassificationsCard /></QueryClientProvider>)
    expect(screen.getByText("Not currently classified.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Tier 1" })).not.toBeInTheDocument()
  })

  it("keeps a CNV classification visible while its tier mutations are disabled", () => {
    renderWithQuery(
      <ClassificationsCard
        latest={{ tier: 2, reason: "Existing classification" }}
        sampleId="S1"
        resourceType="cnv"
        resourceId="C1"
      />,
    )

    expect(screen.getByText("Existing classification")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Tier 1" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument()
  })

  it("confirms group deactivation with its scope and retains historical status", async () => {
    patch.mockClear()
    patch.mockResolvedValueOnce({ ok: true })
    renderWithQuery(<ClassificationsCard latest={{ class: 2, is_active: false, historical_sample_match: true }}
      sampleId="S1" resourceType="small_variant" resourceId="V1" />)
    expect(screen.getByText("Inactive")).toBeVisible()
    expect(screen.getByText(/Historical annotation linked to this sample/)).toBeVisible()
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument()
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "Deactivate group annotations" }))
    expect(screen.getByText(/every assay and diagnosis in the biological group/)).toBeVisible()
    expect(patch).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "Deactivate annotations" }))
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/samples/S1/classifications/tier", {
      resource_type: "small_variant", resource_ids: ["V1"], tier: 2, apply: false,
      deactivation_scope: "group",
    }))
  })
})
