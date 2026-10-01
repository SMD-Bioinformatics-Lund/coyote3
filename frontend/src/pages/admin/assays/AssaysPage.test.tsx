import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssaysPage } from "./AssaysPage";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  permissions: [
    "assay.panel:list",
    "assay.panel:view",
    "assay.panel:create",
    "assay.panel:edit",
    "assay.panel:delete",
  ],
}));
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }));
vi.mock("@/lib/access-control", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/access-control")>();
  return {
    ...actual,
    useCurrentUserAccess: () => ({
      data: { username: "assay_reviewer", roles: [], permissions: mocks.permissions },
      isLoading: false,
    }),
  };
});

function mount() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <MemoryRouter>
        <AssaysPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Assays page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.permissions = [
      "assay.panel:list",
      "assay.panel:view",
      "assay.panel:create",
      "assay.panel:edit",
      "assay.panel:delete",
    ];
    mocks.get.mockResolvedValue({
      data: {
        panels: [
          {
            asp_id: "demo_dna",
            display_name: "Demo DNA",
            asp_category: "dna",
            asp_group: "demo",
            covered_genes_count: 3,
            is_active: true,
            system_managed: true,
          },
          {
            asp_id: "demo_rna",
            display_name: "Demo RNA",
            asp_category: "rna",
            asp_group: "demo",
            covered_genes_count: 0,
            is_active: true,
            system_managed: false,
          },
        ],
      },
    });
  });

  it("owns assay columns and filters without exposing account actions", async () => {
    mount();
    expect(await screen.findByText("demo_dna")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: /Assay ID/i })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: /Actions/ })).toBeVisible();
    expect(screen.queryByTitle("Invite user")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Assay category"), { target: { value: "rna" } });
    expect(screen.queryByText("demo_dna")).not.toBeInTheDocument();
    expect(screen.getByText("demo_rna")).toBeVisible();
    expect(mocks.get).toHaveBeenCalledWith("/resources/asp?per_page=200");
  });

  it("links creation to setup and protects installed assays from deletion", async () => {
    mount();
    const row = (await screen.findByText("demo_dna")).closest("tr")!;
    expect(screen.getByRole("link", { name: "Create" })).toHaveAttribute(
      "href",
      "/admin/assay-setups?setup=new",
    );
    expect(within(row).getByTitle("Edit")).toHaveAttribute("href", "/admin/asp/demo_dna/edit");
    expect(within(row).getByTitle("Toggle active")).toBeEnabled();
    expect(within(row).queryByTitle("Delete")).not.toBeInTheDocument();
    const customRow = screen.getByText("demo_rna").closest("tr")!;
    expect(within(customRow).getByTitle("Delete")).toBeEnabled();
  });

  it("shows covered gene counts instead of gene names, including zero for an empty list", async () => {
    mount();
    const dnaRow = (await screen.findByText("demo_dna")).closest("tr")!;
    const rnaRow = screen.getByText("demo_rna").closest("tr")!;
    expect(screen.getByRole("columnheader", { name: /Covered Genes/ })).toBeVisible();
    expect(within(dnaRow).getByRole("cell", { name: "3" })).toBeVisible();
    expect(within(rnaRow).getByRole("cell", { name: "0" })).toBeVisible();
    expect(screen.queryByText(/BRAF|EGFR|KRAS/)).not.toBeInTheDocument();
  });

  it("keeps the assay list read-only for viewers", async () => {
    mocks.permissions = ["assay.panel:list", "assay.panel:view"];
    mount();
    const row = (await screen.findByText("demo_rna")).closest("tr")!;
    expect(within(row).getByTitle("View")).toHaveAttribute("href", "/admin/asp/demo_rna/view");
    expect(within(row).queryByTitle("Edit")).not.toBeInTheDocument();
    expect(within(row).queryByTitle("Delete")).not.toBeInTheDocument();
    expect(within(row).queryByTitle("Toggle active")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Create" })).not.toBeInTheDocument();
  });
});
