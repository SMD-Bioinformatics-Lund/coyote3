import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { uiRouteRegistry } from "@/lib/routes/ui-route-registry"

const mocks = vi.hoisted(() => ({ table: vi.fn() }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    const data = props.data as Record<string, any>[]
    const columns = props.columns as Record<string, any>[]
    const rows = [
      data.find((route) => route.api.length > 0),
      data.find((route) => route.api.length === 0),
    ].filter(Boolean) as Record<string, any>[]
    return (
      <div data-testid="route-audit-table">
        {data.length} routes
        {rows.map((original, rowIndex) => (
          <div data-testid={`audit-row-${rowIndex}`} key={original.path}>
            {columns.map((column, columnIndex) => {
              const id = column.id || column.accessorKey || `column-${columnIndex}`
              const row = {
                original,
                getValue: (requestedId: string) => original[requestedId],
              }
              return (
                <div data-testid={`audit-cell-${rowIndex}-${id}`} key={id}>
                  {column.cell
                    ? column.cell({ row })
                    : String(column.accessorFn ? column.accessorFn(original) : original[column.accessorKey] ?? "")}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    )
  },
}))

import { UiRouteAuditPage } from "./UiRouteAuditPage"

describe("UiRouteAuditPage", () => {
  it("passes the complete route registry to an exportable audit table", () => {
    render(<MemoryRouter><UiRouteAuditPage /></MemoryRouter>)

    expect(screen.getByRole("heading", { name: "UI Route & Data Audit" })).toBeVisible()
    expect(screen.getByTestId("route-audit-table")).toHaveTextContent(`${uiRouteRegistry.length} routes`)
    expect(mocks.table).toHaveBeenCalledWith(expect.objectContaining({
      data: uiRouteRegistry,
      filename: "coyote3-ui-route-audit.csv",
    }))
    expect(screen.getByTestId("audit-cell-0-api")).toHaveTextContent(uiRouteRegistry.find((route) => route.api.length)?.api[0] || "")
    expect(screen.getByTestId("audit-cell-0-dataUsed")).not.toBeEmptyDOMElement()
    expect(screen.getByTestId("audit-cell-0-states")).toHaveTextContent("Empty:")
    expect(screen.getByTestId("audit-cell-0-states")).toHaveTextContent("Error:")
    expect(screen.getByTestId("audit-cell-1-api")).toHaveTextContent("No remote data")
  })

  it("reports the exact API-backed route count", () => {
    render(<MemoryRouter><UiRouteAuditPage /></MemoryRouter>)
    const expected = uiRouteRegistry.filter((route) => route.api.length).length

    expect(screen.getByText(`${expected}/${uiRouteRegistry.length} API-backed`)).toBeVisible()
  })
})
