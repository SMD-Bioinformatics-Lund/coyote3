import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
  getFilteredRowModel,
} from "@tanstack/react-table"
import { useEffect, useState, type ReactNode } from "react"
import { Search, ArrowDownToLine, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react"
import { shortCount } from "@/lib/detail-formatters"
import { cn } from "@/lib/utils"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  filename?: string
  rowLabel?: string
  totalCount?: number
  page?: number
  perPage?: number
  hasNext?: boolean
  hasPrevious?: boolean
  onPageChange?: (page: number) => void
  onPerPageChange?: (perPage: number) => void
  renderToolbar?: (table: any) => ReactNode
  renderExportButton?: (table: any) => ReactNode
  hideExport?: boolean
  hideSearch?: boolean
  getRowClassName?: (row: TData) => string
}

const RENDER_BATCH_SIZE = 300

export function DataTable<TData, TValue>({
  columns,
  data,
  filename = "export.csv",
  rowLabel = "rows",
  totalCount,
  page = 1,
  perPage,
  hasNext = false,
  hasPrevious = false,
  onPageChange,
  onPerPageChange,
  renderToolbar,
  renderExportButton,
  hideExport = false,
  hideSearch = false,
  getRowClassName,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState("")
  const [rowSelection, setRowSelection] = useState({})
  const [renderLimit, setRenderLimit] = useState(RENDER_BATCH_SIZE)

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      globalFilter,
      rowSelection,
    },
  })

  const exportToCSV = () => {
    const headers = table.getAllLeafColumns()
      .filter(col => col.id !== "actions" && col.id !== "select")
      .map(col => {
        return `"${col.columnDef.header?.toString() || col.id}"`
      })
      .join(",")

    const rows = table.getRowModel().rows.map(row => {
      return table.getAllLeafColumns()
        .filter(col => col.id !== "actions" && col.id !== "select")
        .map(col => {
          const exportValue = (col.columnDef.meta as any)?.exportValue
          const val = typeof exportValue === "function"
            ? exportValue(row.original)
            : row.getValue(col.id)
          const strVal = typeof val === 'object' && val !== null ? JSON.stringify(val) : String(val ?? "")
          return `"${strVal.replace(/"/g, '""')}"`
        })
        .join(",")
    }).join("\n")

    const csvContent = `${headers}\n${rows}`
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement("a")
    const url = URL.createObjectURL(blob)
    link.setAttribute("href", url)
    link.setAttribute("download", filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const columnAlign = (columnId: string) => columnId === "tier" ? "center" : "left"
  const defaultColumnClass = (columnId: string) => {
    if (columnId === "badges") return "w-14 min-w-14 max-w-14"
    if (columnId === "tier") return "w-10 min-w-10 max-w-10"
    return ""
  }
  const returnedCount = totalCount ?? data.length
  const serverPaginated = Boolean(onPageChange)
  const allRows = table.getRowModel().rows
  const visibleRows = allRows.slice(0, renderLimit)
  const hasMoreRows = visibleRows.length < allRows.length
  const rangeStart = returnedCount === 0 ? 0 : (page - 1) * (perPage ?? allRows.length) + 1
  const rangeEnd = Math.min(
    returnedCount,
    (page - 1) * (perPage ?? allRows.length) + visibleRows.length,
  )

  useEffect(() => {
    setRenderLimit(RENDER_BATCH_SIZE)
  }, [data.length, globalFilter, sorting])

  return (
    <div className="flex min-w-0 flex-col">
      {/* Table Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-0.5 pb-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="rounded-lg border border-border bg-muted/60 px-2.5 py-1.5 text-xs font-black text-foreground shadow-sm">
            {shortCount(returnedCount)} {rowLabel}
          </div>
          {!hideSearch && (
            <div className="relative w-56 sm:w-64">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
              <input
                placeholder="Search all columns..."
                value={globalFilter ?? ""}
                onChange={(event) => setGlobalFilter(event.target.value)}
                className="w-full rounded-lg border border-input bg-background/80 py-1.5 pl-9 pr-3 text-xs shadow-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:bg-background focus:ring-3 focus:ring-ring/30 dark:bg-input/30"
              />
            </div>
          )}
          {renderToolbar && renderToolbar(table)}
        </div>
        {!hideExport && (
          <div className="ml-auto flex shrink-0 items-center">
            {renderExportButton ? renderExportButton(table) : (
              <button
                onClick={exportToCSV}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground shadow-sm shadow-primary/20 transition-colors hover:bg-primary/90"
              >
                <ArrowDownToLine className="h-4 w-4" />
                Export to CSV
              </button>
            )}
          </div>
        )}
      </div>

      {/* Table Area */}
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm [contain:paint]">
        <div className="overflow-x-auto">
          <table className="w-full table-auto border-separate border-spacing-0 text-left text-sm tabular-nums">
            <thead className="border-b-2 border-border bg-muted text-[11px] font-black uppercase tracking-wide text-foreground shadow-sm dark:bg-muted/70">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const align = columnAlign(header.column.id)
                    const meta = header.column.columnDef.meta as any
                    const sortedIcon = {
                      asc: <ArrowUp className="h-3 w-3 shrink-0" />,
                      desc: <ArrowDown className="h-3 w-3 shrink-0" />,
                    }[header.column.getIsSorted() as string] ?? (
                      header.column.getCanSort() ? <ArrowUpDown className="h-3 w-3 shrink-0 opacity-30" /> : null
                    )
                    return (
                      <th
                        key={header.id}
                        className={cn(
                            "whitespace-normal break-words border-b-2 border-r border-border px-1.5 py-1.5 align-bottom leading-tight last:border-r-0",
                          align === "center" ? "text-center" : "text-left",
                          defaultColumnClass(header.column.id),
                          meta?.headerClassName,
                        )}
                      >
                        {header.isPlaceholder ? null : (
                          <div
                            className={cn(
                              "flex min-h-10 items-end gap-0.5",
                              align === "center" ? "justify-center" : "justify-start",
                              header.column.getCanSort() ? "cursor-pointer select-none hover:text-foreground transition-colors" : ""
                            )}
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            <span className="min-w-0 break-words leading-tight">
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                            </span>
                            {sortedIcon}
                          </div>
                        )}
                      </th>
                    )
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {allRows.length ? (
                visibleRows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn("transition-colors duration-75 odd:bg-background/35 even:bg-card/60 hover:bg-primary/10 dark:hover:bg-primary/20", getRowClassName?.(row.original) ?? "")}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const align = columnAlign(cell.column.id)
                      const meta = cell.column.columnDef.meta as any
                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            "border-b border-r border-border/65 px-1.5 py-1.5 align-middle last:border-r-0",
                            align === "center" ? "text-center" : "text-left",
                            defaultColumnClass(cell.column.id),
                            meta?.cellClassName,
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      )
                    })}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={columns.length} className="h-24 text-center text-muted-foreground font-medium">
                    No results found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 px-1 py-2 text-xs font-medium text-muted-foreground">
        <span>
          {serverPaginated
            ? `Showing ${rangeStart}-${rangeEnd} of ${shortCount(returnedCount)} ${rowLabel}`
            : `Showing ${visibleRows.length} of ${allRows.length} row(s)`}
        </span>
        {serverPaginated && onPerPageChange && (
          <select
            value={perPage ?? 50}
            onChange={(event) => onPerPageChange(Number(event.target.value))}
            className="rounded-lg border border-border bg-card px-2 py-1 text-xs font-bold text-foreground shadow-sm outline-none focus:ring-3 focus:ring-ring/30"
          >
            {[25, 50, 100, 200].map((value) => (
              <option key={value} value={value}>
                {value} / page
              </option>
            ))}
          </select>
        )}
        {serverPaginated && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={!hasPrevious}
              onClick={() => onPageChange?.(Math.max(1, page - 1))}
              className="rounded-lg border border-border bg-card px-2.5 py-1 font-bold text-foreground shadow-sm transition-colors duration-100 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
            >
              Previous
            </button>
            <span className="px-1 font-bold text-foreground">Page {page}</span>
            <button
              type="button"
              disabled={!hasNext}
              onClick={() => onPageChange?.(page + 1)}
              className="rounded-lg border border-border bg-card px-2.5 py-1 font-bold text-foreground shadow-sm transition-colors duration-100 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
            >
              Next
            </button>
          </div>
        )}
        {!serverPaginated && hasMoreRows && (
          <button
            type="button"
            onClick={() => setRenderLimit((current) => current + RENDER_BATCH_SIZE)}
            className="rounded-lg border border-border bg-card px-2.5 py-1 font-bold text-foreground shadow-sm transition-colors duration-100 hover:bg-muted"
          >
            Show more
          </button>
        )}
      </div>
    </div>
  )
}
