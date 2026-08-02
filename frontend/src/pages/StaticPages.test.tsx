import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))
vi.mock("@/lib/runtime-config", () => ({ runtimeConfig: { organizationName: "Fallback Center" } }))
vi.mock("@/lib/runtime-paths", () => ({ appPath: (path: string) => `/coyote3${path}` }))

import { AboutPage, ContactPage, NotFoundPage } from "./StaticPages"

function mount(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const publicPayload = {
  organization: {
    name: "Molecular Diagnostics",
    department: "Clinical Genomics",
    description: "Clinical interpretation service.",
    address: "Hospital Road 1\nLund",
  },
  support: { primary_email: "support@example.org", urgent_phone: "+461234" },
  contacts: [
    {
      label: "Clinical support",
      role: "Interpretation",
      description: "Questions about clinical reports.",
      email: "clinical@example.org",
      phone: "+465678",
    },
  ],
  hours: [{ label: "Service desk", value: "Weekdays 08:00-16:30" }],
  links: [
    { label: "Documentation", url: "/docs-site/", description: "User guide", icon: "docs" },
    { label: "External help", url: "https://example.org/help", icon: "issue" },
  ],
  codebase: {
    repository_url: "https://github.com/example/coyote3",
    license_url: "https://github.com/example/coyote3/LICENSE.txt",
    bug_report_url: "https://github.com/example/coyote3/issues/new?template=bug.md",
    feature_request_url: "https://github.com/example/coyote3/issues/new?template=feature.md",
    support_request_url: "https://github.com/example/coyote3/issues/new?template=support.md",
  },
  application: { version: "4.0.0", environment: "production", description: "Coyote3" },
  references: {
    vep_metadata: ["103", "110"],
    sample_database_versions: { assembly: "GRCh38.p13", clinvar: "202008" },
  },
  software: { vep: ["103"], pipelines: { SomaticPanelPipeline: "3.2.0" } },
  databases: {
    primary: "coyote3",
    bam_service: "BAM_Service",
    knowledgebases: { oncokb: "https://public.api.oncokb.org/api/v1" },
  },
}

describe("public static pages", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: publicPayload })
  })

  it("renders configured contact channels, hours, address, and prefixed internal links", async () => {
    mount(<ContactPage />)

    expect(await screen.findByRole("heading", { name: "Molecular Diagnostics" })).toBeVisible()
    expect(screen.getByRole("link", { name: /clinical@example.org/ })).toHaveAttribute("href", "mailto:clinical@example.org")
    expect(screen.getByRole("link", { name: /\+465678/ })).toHaveAttribute("href", "tel:+465678")
    expect(screen.getByText("Weekdays 08:00-16:30")).toBeVisible()
    expect(screen.getByText(/Hospital Road 1/)).toBeVisible()
    expect(screen.getByRole("link", { name: /Documentation/ })).toHaveAttribute("href", "/coyote3/docs-site/")
    expect(screen.getByRole("link", { name: /External help/ })).toHaveAttribute("target", "_blank")
    expect(mocks.get).toHaveBeenCalledWith("/public/contact")
  })

  it("uses safe empty states when optional contact configuration is absent", async () => {
    mocks.get.mockResolvedValue({ data: { organization: {}, contacts: [], hours: [], links: [], support: {} } })
    mount(<ContactPage />)

    expect(await screen.findByRole("heading", { name: "Fallback Center" })).toBeVisible()
    expect(screen.getByText("No contact channels are configured yet.")).toBeVisible()
    expect(screen.queryByText("Primary Support")).not.toBeInTheDocument()
    expect(screen.queryByText("Service Hours")).not.toBeInTheDocument()
  })

  it("renders application, pipeline, reference, database, and codebase metadata", async () => {
    mount(<AboutPage />)

    expect(await screen.findByText("4.0.0")).toBeVisible()
    expect(screen.getByText("Environment: production")).toBeVisible()
    expect(screen.getByText("coyote3")).toBeVisible()
    expect(screen.getByText("BAM service: BAM_Service")).toBeVisible()
    expect(screen.getByText("SomaticPanelPipeline")).toBeVisible()
    expect(screen.getByText("GRCh38.p13")).toBeVisible()
    expect(screen.getByText("https://public.api.oncokb.org/api/v1")).toBeVisible()
    expect(screen.getByRole("link", { name: "License" })).toHaveAttribute("target", "_blank")
    expect(screen.getByRole("link", { name: /Report a Bug/ })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/public/about")
  })

  it("deduplicates configured and default about links by URL", async () => {
    mount(<AboutPage />)
    await screen.findByText("4.0.0")

    expect(screen.getAllByRole("link", { name: /Documentation/ })).toHaveLength(1)
  })

  it("provides a navigable not-found state", () => {
    mount(<NotFoundPage />)

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeVisible()
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/")
  })
})
