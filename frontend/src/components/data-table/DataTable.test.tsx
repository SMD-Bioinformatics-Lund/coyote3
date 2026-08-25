import type { ColumnDef } from "@tanstack/react-table"
import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { DataTable } from "./DataTable"
import { csvCellText } from "@/lib/csv-export"

type Row = { gene: string; tier: number; note: string }

const columns: ColumnDef<Row>[] = [
  { accessorKey: "gene", header: "Gene" },
  { accessorKey: "tier", header: "Tier" },
  { accessorKey: "note", header: "Note", enableSorting: false },
]

const data: Row[] = [
  { gene: "TP53", tier: 2, note: "second" },
  { gene: "ABL1", tier: 1, note: "first" },
]

describe("DataTable", () => {
  it("deduplicates list-valued CSV cells while preserving their order", () => {
    expect(csvCellText(["fusioncatcher", "FusionCatcher", "starfusion"])).toBe(
      "fusioncatcher | starfusion",
    )
    expect(csvCellText(["PASS", "WARN", "PASS"])).toBe("PASS | WARN")
  })

  it("filters rows, persists search, and reports empty results", async () => {
    const user = userEvent.setup()
    const { rerender } = render(<DataTable columns={columns} data={data} filename="variants.csv" />)
    const search = screen.getByPlaceholderText("Search all columns...")
    await user.type(search, "TP53")
    expect(screen.getByText("TP53")).toBeVisible()
    expect(screen.queryByText("ABL1")).not.toBeInTheDocument()
    expect(sessionStorage.getItem("coyote3.table.variants.csv.search")).toBe("TP53")

    rerender(<DataTable columns={columns} data={data} filename="variants.csv" />)
    expect(search).toHaveValue("TP53")
    await user.clear(search)
    await user.type(search, "missing")
    expect(screen.getByText("No results found.")).toBeVisible()
  })

  it("supports additive multi-column sorting and stores its state", async () => {
    const user = userEvent.setup()
    render(<DataTable columns={columns} data={data} stateKey="variant-list" />)
    await user.click(screen.getByText("Gene"))
    await user.click(screen.getByText("Tier"))
    expect(JSON.parse(sessionStorage.getItem("coyote3.table.variant-list.sorting") || "[]")).toEqual([
      { id: "gene", desc: false },
      { id: "tier", desc: true },
    ])
    expect(screen.getAllByText(/[12]/).length).toBeGreaterThan(1)
  })

  it("uses controlled search and server pagination callbacks", async () => {
    const user = userEvent.setup()
    const onSearchChange = vi.fn()
    const onPageChange = vi.fn()
    const onPerPageChange = vi.fn()
    render(
      <DataTable
        columns={columns}
        data={data}
        totalCount={12}
        page={2}
        perPage={2}
        hasNext
        hasPrevious
        onPageChange={onPageChange}
        onPerPageChange={onPerPageChange}
        searchValue="TP"
        onSearchChange={onSearchChange}
        hideExport
      />,
    )

    await user.type(screen.getByPlaceholderText("Search all columns..."), "5")
    expect(onSearchChange).toHaveBeenCalledWith("TP5")
    await user.click(screen.getByRole("button", { name: "Previous" }))
    await user.click(screen.getByRole("button", { name: "Next" }))
    expect(onPageChange).toHaveBeenNthCalledWith(1, 1)
    expect(onPageChange).toHaveBeenNthCalledWith(2, 3)
    await user.selectOptions(screen.getByRole("combobox"), "100")
    expect(onPerPageChange).toHaveBeenCalledWith(100)
    expect(screen.getByText("Showing 3-4 of 12 rows")).toBeVisible()
  })

  it("paginates local result sets without dropping rows from the result count", async () => {
    const user = userEvent.setup()
    const rows = Array.from({ length: 55 }, (_, index) => ({
      gene: `GENE${index + 1}`,
      tier: (index % 4) + 1,
      note: `row ${index + 1}`,
    }))
    render(<DataTable columns={columns} data={rows} hideExport />)

    expect(screen.getByText("GENE1")).toBeVisible()
    expect(screen.queryByText("GENE51")).not.toBeInTheDocument()
    expect(screen.getByText("Showing 1-50 of 55 row(s)")).toBeVisible()

    await user.click(screen.getByRole("button", { name: "Next" }))
    expect(screen.getByText("GENE51")).toBeVisible()
    expect(screen.queryByText("GENE1")).not.toBeInTheDocument()
    expect(screen.getByText("Showing 51-55 of 55 row(s)")).toBeVisible()
  })

  it("exports visible values and excludes action columns", () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    const exportColumns: ColumnDef<Row>[] = [
      ...columns,
      { id: "actions", header: "Actions", cell: () => "Open" },
    ]
    render(<DataTable columns={exportColumns} data={data} filename="findings.csv" />)
    fireEvent.click(screen.getByRole("button", { name: "Export to CSV" }))
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
  })

  it("uses explicit export columns and keeps missing values empty", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    render(
      <DataTable
        columns={columns}
        data={data}
        filename="samples.csv"
        exportColumns={[
          { header: "Gene", value: (row) => row.gene },
          { header: "Biomarker HRD.sum", value: () => "" },
        ]}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Export to CSV" }))

    const blob = vi.mocked(URL.createObjectURL).mock.calls.at(-1)?.[0] as Blob
    expect(await blob.text()).toBe('"Gene","Biomarker HRD.sum"\n"TP53",""\n"ABL1",""')
    expect(click).toHaveBeenCalledOnce()
  })

  it("applies row classes and optional toolbar content", () => {
    render(
      <DataTable
        columns={columns}
        data={data}
        hideSearch
        hideExport
        getRowClassName={(row) => row.gene === "TP53" ? "flagged" : ""}
        renderToolbar={() => <button>Bulk action</button>}
      />,
    )
    expect(screen.getByRole("button", { name: "Bulk action" })).toBeVisible()
    expect(within(screen.getByText("TP53").closest("tr") as HTMLElement).getByText("second")).toBeVisible()
    expect(screen.getByText("TP53").closest("tr")).toHaveClass("flagged")
  })
})
