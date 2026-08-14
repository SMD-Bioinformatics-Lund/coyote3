import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
  getFilteredRowModel,
  type OnChangeFn,
} from "@tanstack/react-table"
import { useEffect, useState, type ReactNode } from "react"
import { Search, ArrowDownToLine, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react"
import { shortCount } from "@/lib/detail-formatters"
import { cn } from "@/lib/utils"
import { csvCellText } from "@/lib/csv-export"
import { TableBadge } from "@/components/ui/table-badge"

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
  searchValue?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  getRowClassName?: (row: TData) => string
  sortingState?: SortingState
  onSortingChange?: (sorting: SortingState) => void
  manualSorting?: boolean
  stateKey?: string
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
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search all columns...",
  getRowClassName,
  sortingState,
  onSortingChange,
  manualSorting = false,
  stateKey,
}: DataTableProps<TData, TValue>) {
  const tableStateKey = `coyote3.table.${stateKey || filename}`
  const [internalSorting, setInternalSorting] = useState<SortingState>(() => {
    if (typeof window === "undefined" || sortingState) return []
    try {
      const raw = window.sessionStorage.getItem(`${tableStateKey}.sorting`)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  })
  const [globalFilter, setGlobalFilter] = useState(() => {
    if (typeof window === "undefined" || typeof onSearchChange === "function") return ""
    return window.sessionStorage.getItem(`${tableStateKey}.search`) || ""
  })
  const [rowSelection, setRowSelection] = useState({})
  const [renderLimit, setRenderLimit] = useState(RENDER_BATCH_SIZE)
  const controlledSearch = typeof onSearchChange === "function"
  const displayedSearchValue = controlledSearch ? (searchValue ?? "") : (globalFilter ?? "")
  const sorting = sortingState ?? internalSorting
  const handleSortingChange: OnChangeFn<SortingState> = (updater) => {
    const nextSorting = typeof updater === "function" ? updater(sorting) : updater
    if (onSortingChange) {
      onSortingChange(nextSorting)
      return
    }
    setInternalSorting(nextSorting)
  }

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    ...(manualSorting ? {} : { getSortedRowModel: getSortedRowModel() }),
    manualSorting,
    enableMultiSort: true,
    isMultiSortEvent: () => true,
    onSortingChange: handleSortingChange,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      globalFilter: controlledSearch ? "" : globalFilter,
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
          const strVal = csvCellText(val)
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
    if (columnId === "tier") return "w-14 min-w-14"
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
  }, [data.length, displayedSearchValue, sorting])

  useEffect(() => {
    if (typeof window === "undefined" || sortingState) return
    window.sessionStorage.setItem(`${tableStateKey}.sorting`, JSON.stringify(internalSorting))
  }, [internalSorting, sortingState, tableStateKey])

  useEffect(() => {
    if (typeof window === "undefined" || controlledSearch) return
    if (globalFilter) window.sessionStorage.setItem(`${tableStateKey}.search`, globalFilter)
    else window.sessionStorage.removeItem(`${tableStateKey}.search`)
  }, [controlledSearch, globalFilter, tableStateKey])

  return (
    <div className="flex min-w-0 flex-col">
      {/* Table Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1.5 pb-3 pt-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {!hideSearch && (
            <div className="search-field relative w-56 rounded-xl sm:w-64">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-primary/75" />
              <input
                placeholder={searchPlaceholder}
                value={displayedSearchValue}
                onChange={(event) => {
                  const value = event.target.value
                  if (controlledSearch) {
                    onSearchChange?.(value)
                    return
                  }
                  setGlobalFilter(value)
                }}
                className="w-full rounded-xl border-0 bg-transparent py-1.5 pl-9 pr-3 text-xs outline-none transition-colors placeholder:text-muted-foreground focus:bg-transparent"
              />
            </div>
          )}
          <TableBadge className="border-border bg-muted/70 font-semibold text-foreground shadow-none">
            {shortCount(returnedCount)} {rowLabel}
          </TableBadge>
          {renderToolbar && renderToolbar(table)}
        </div>
        {!hideExport && (
          <div className="ml-auto flex shrink-0 items-center">
            {renderExportButton ? renderExportButton(table) : (
              <button
                onClick={exportToCSV}
                className="inline-flex items-center gap-2 rounded-lg border border-primary/75 bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground shadow-[0_2px_6px_color-mix(in_srgb,var(--primary)_24%,transparent)] transition-colors hover:bg-primary/90"
              >
                <ArrowDownToLine className="h-4 w-4" />
                Export to CSV
              </button>
            )}
          </div>
        )}
      </div>

      {/* Table Area */}
      <div className="paper-surface overflow-hidden rounded-lg [contain:paint]">
        <div className="overflow-x-auto">
          <table className="w-full table-auto border-separate border-spacing-0 text-left text-[0.84rem] tabular-nums">
            <thead className="type-table-header border-b-2 border-border bg-[var(--header-surface)] text-foreground">
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
                    const sortIndex = sorting.findIndex((item) => item.id === header.column.id)
                    return (
                      <th
                        key={header.id}
                        className={cn(
                            "whitespace-normal break-words border-b-2 border-r border-border px-2 py-1 align-bottom leading-tight last:border-r-0",
                          align === "center" ? "text-center" : "text-left",
                          defaultColumnClass(header.column.id),
                          meta?.headerClassName,
                        )}
                      >
                        {header.isPlaceholder ? null : (
                          <div
                            className={cn(
                              "flex min-h-7 items-end gap-0.5",
                              align === "center" ? "justify-center" : "justify-start",
                              header.column.getCanSort() ? "cursor-pointer select-none hover:text-foreground transition-colors" : ""
                            )}
                            title={header.column.getCanSort() ? "Click to add or cycle this column in the multi-column sort order." : undefined}
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            <span className={cn("min-w-0 break-words leading-tight", header.column.id === "tier" && "whitespace-nowrap break-normal")}>
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                            </span>
                            {sortedIcon}
                            {sortIndex >= 0 && sorting.length > 1 && (
                              <span className="ml-0.5 rounded-full bg-primary/15 px-1 text-[9px] font-black leading-4 text-primary">
                                {sortIndex + 1}
                              </span>
                            )}
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
                    className={cn("bg-[var(--paper-raised)] transition-colors duration-75 hover:bg-primary/10", getRowClassName?.(row.original) ?? "")}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const align = columnAlign(cell.column.id)
                      const meta = cell.column.columnDef.meta as any
                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            "border-b border-r border-border/40 px-2 py-1.5 align-middle last:border-r-0",
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
      <div className="mt-2 flex min-h-11 items-center justify-end gap-2 border-t border-border/60 px-2 py-2.5 text-xs font-medium text-muted-foreground">
        <span>
          {serverPaginated
            ? `Showing ${rangeStart}-${rangeEnd} of ${shortCount(returnedCount)} ${rowLabel}`
            : `Showing ${visibleRows.length} of ${allRows.length} row(s)`}
        </span>
        {serverPaginated && onPerPageChange && (
          <select
            value={perPage ?? 50}
            onChange={(event) => onPerPageChange(Number(event.target.value))}
            className="paper-inset rounded-lg px-2 py-1 text-xs font-bold text-foreground outline-none focus:ring-3 focus:ring-ring/30"
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
              className="paper-inset rounded-lg px-2.5 py-1 font-bold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
            >
              Previous
            </button>
            <span className="px-1 font-bold text-foreground">Page {page}</span>
            <button
              type="button"
              disabled={!hasNext}
              onClick={() => onPageChange?.(page + 1)}
              className="paper-inset rounded-lg px-2.5 py-1 font-bold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
            >
              Next
            </button>
          </div>
        )}
        {!serverPaginated && hasMoreRows && (
          <button
            type="button"
            onClick={() => setRenderLimit((current) => current + RENDER_BATCH_SIZE)}
            className="paper-inset rounded-lg px-2.5 py-1 font-bold text-foreground hover:border-primary/30 hover:bg-muted"
          >
            Show more
          </button>
        )}
      </div>
    </div>
  )
}
