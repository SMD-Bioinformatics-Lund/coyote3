import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
  getFilteredRowModel,
  getPaginationRowModel,
  type PaginationState,
  type OnChangeFn,
} from "@tanstack/react-table";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Search, ArrowDownToLine, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { shortCount } from "@/lib/detail-formatters";
import { cn } from "@/lib/utils";
import { csvCellText } from "@/lib/csv-export";
import { TableBadge } from "@/components/ui/table-badge";
import { useTablePreferences } from "@/components/data-table/table-preferences";
import {
  resolveTableDensity,
  resolveTableMinimumWidth,
} from "@/components/data-table/table-density";
import { PageSizeSelect } from "@/components/data-table/PageSizeSelect";
import { downloadText } from "@/lib/browser-download";

export interface CsvExportColumn<TData> {
  header: string;
  value: (row: TData) => unknown;
}

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  filename?: string;
  rowLabel?: string;
  totalCount?: number;
  page?: number;
  perPage?: number;
  hasNext?: boolean;
  hasPrevious?: boolean;
  onPageChange?: (page: number) => void;
  onPerPageChange?: (perPage: number) => void;
  renderToolbar?: (table: any) => ReactNode;
  renderExportButton?: (table: any) => ReactNode;
  hideExport?: boolean;
  hideSearch?: boolean;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  getRowClassName?: (row: TData) => string;
  sortingState?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  manualSorting?: boolean;
  stateKey?: string;
  enablePagination?: boolean;
  exportColumns?: CsvExportColumn<TData>[];
}

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
  enablePagination = true,
  exportColumns,
}: DataTableProps<TData, TValue>) {
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const [tableContainerWidth, setTableContainerWidth] = useState(0);
  const { pageSize: preferredPageSize, setPageSize: persistPageSize } = useTablePreferences();
  const serverPaginated = Boolean(onPageChange);
  const effectivePageSize = perPage ?? preferredPageSize;
  const tableStateKey = `coyote3.table.${stateKey || filename}`;
  const [internalSorting, setInternalSorting] = useState<SortingState>(() => {
    if (typeof window === "undefined" || sortingState) return [];
    try {
      const raw = window.sessionStorage.getItem(`${tableStateKey}.sorting`);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [globalFilter, setGlobalFilter] = useState(() => {
    if (typeof window === "undefined" || typeof onSearchChange === "function") return "";
    return window.sessionStorage.getItem(`${tableStateKey}.search`) || "";
  });
  const [rowSelection, setRowSelection] = useState({});
  const [clientPagination, setClientPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: effectivePageSize,
  });
  const controlledSearch = typeof onSearchChange === "function";
  const displayedSearchValue = controlledSearch ? (searchValue ?? "") : (globalFilter ?? "");
  const sorting = sortingState ?? internalSorting;
  const handleSortingChange: OnChangeFn<SortingState> = (updater) => {
    const nextSorting = typeof updater === "function" ? updater(sorting) : updater;
    if (onSortingChange) {
      onSortingChange(nextSorting);
      return;
    }
    setInternalSorting(nextSorting);
  };

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    ...(!serverPaginated && enablePagination
      ? { getPaginationRowModel: getPaginationRowModel() }
      : {}),
    ...(manualSorting ? {} : { getSortedRowModel: getSortedRowModel() }),
    manualSorting,
    enableMultiSort: true,
    isMultiSortEvent: () => true,
    onSortingChange: handleSortingChange,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    onPaginationChange: setClientPagination,
    manualPagination: serverPaginated,
    state: {
      sorting,
      globalFilter: controlledSearch ? "" : globalFilter,
      rowSelection,
      pagination: serverPaginated
        ? { pageIndex: Math.max(0, page - 1), pageSize: effectivePageSize }
        : clientPagination,
    },
  });

  const exportToCSV = () => {
    if (exportColumns?.length) {
      const headers = exportColumns
        .map(({ header }) => `"${header.replace(/"/g, '""')}"`)
        .join(",");
      const rows = table
        .getPrePaginationRowModel()
        .rows.map(({ original }) =>
          exportColumns
            .map(({ value }) => {
              const strVal = csvCellText(value(original));
              return `"${strVal.replace(/"/g, '""')}"`;
            })
            .join(","),
        )
        .join("\n");
      downloadCsv(`${headers}\n${rows}`, filename);
      return;
    }
    const headers = table
      .getAllLeafColumns()
      .filter((col) => col.id !== "actions" && col.id !== "select")
      .map((col) => {
        return `"${col.columnDef.header?.toString() || col.id}"`;
      })
      .join(",");

    const rows = table
      .getPrePaginationRowModel()
      .rows.map((row) => {
        return table
          .getAllLeafColumns()
          .filter((col) => col.id !== "actions" && col.id !== "select")
          .map((col) => {
            const exportValue = (col.columnDef.meta as any)?.exportValue;
            const val =
              typeof exportValue === "function" ? exportValue(row.original) : row.getValue(col.id);
            const strVal = csvCellText(val);
            return `"${strVal.replace(/"/g, '""')}"`;
          })
          .join(",");
      })
      .join("\n");

    downloadCsv(`${headers}\n${rows}`, filename);
  };

  const downloadCsv = (csvContent: string, downloadFilename: string) => {
    downloadText(csvContent, downloadFilename, "text/csv;charset=utf-8");
  };

  const columnAlign = (columnId: string) =>
    columnId === "tier" || columnId === "select" ? "center" : "left";
  const defaultColumnClass = (columnId: string) => {
    if (columnId === "badges") return "w-14 min-w-14 max-w-14";
    if (columnId === "tier") return "w-14 min-w-14";
    return "";
  };
  const visibleColumnCount = table.getVisibleLeafColumns().length;
  const tableDensity = resolveTableDensity(visibleColumnCount, tableContainerWidth);
  const tableMinimumWidth = resolveTableMinimumWidth(visibleColumnCount, tableDensity);
  const allFilteredRows = table.getPrePaginationRowModel().rows;
  const visibleRows = table.getRowModel().rows;
  const returnedCount = totalCount ?? allFilteredRows.length;
  const clientPage = clientPagination.pageIndex + 1;
  const clientPageCount = Math.max(
    1,
    Math.ceil(allFilteredRows.length / clientPagination.pageSize),
  );
  const paginated =
    serverPaginated || (enablePagination && allFilteredRows.length > clientPagination.pageSize);
  const rangeStart = returnedCount === 0 ? 0 : (page - 1) * effectivePageSize + 1;
  const rangeEnd = Math.min(returnedCount, (page - 1) * effectivePageSize + visibleRows.length);

  useEffect(() => {
    const container = tableContainerRef.current;
    if (!container) return;

    const updateWidth = (width?: number) => {
      const nextWidth = Math.round(width ?? container.getBoundingClientRect().width);
      setTableContainerWidth((current) => (current === nextWidth ? current : nextWidth));
    };
    const handleWindowResize = () => updateWidth();
    updateWidth();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", handleWindowResize);
      return () => window.removeEventListener("resize", handleWindowResize);
    }

    const observer = new ResizeObserver((entries) => {
      updateWidth(entries[0]?.contentRect.width);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setClientPagination((current) => ({
      pageIndex: 0,
      pageSize: serverPaginated ? current.pageSize : preferredPageSize,
    }));
  }, [data.length, displayedSearchValue, preferredPageSize, serverPaginated, sorting]);

  useEffect(() => {
    if (typeof window === "undefined" || sortingState) return;
    window.sessionStorage.setItem(`${tableStateKey}.sorting`, JSON.stringify(internalSorting));
  }, [internalSorting, sortingState, tableStateKey]);

  useEffect(() => {
    if (typeof window === "undefined" || controlledSearch) return;
    if (globalFilter) window.sessionStorage.setItem(`${tableStateKey}.search`, globalFilter);
    else window.sessionStorage.removeItem(`${tableStateKey}.search`);
  }, [controlledSearch, globalFilter, tableStateKey]);

  return (
    <div
      ref={tableContainerRef}
      className="flex min-w-0 flex-col"
      data-table-density={tableDensity}
    >
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
                  const value = event.target.value;
                  if (controlledSearch) {
                    onSearchChange?.(value);
                    return;
                  }
                  setGlobalFilter(value);
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
            {renderExportButton ? (
              renderExportButton(table)
            ) : (
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
      <div className="data-table-frame paper-surface min-w-0 max-w-full overflow-hidden rounded-lg [contain:paint]">
        <div className="data-table-viewport max-w-full overflow-x-auto overscroll-x-contain">
          <table
            className="data-table-grid type-table-cell w-full table-auto border-separate border-spacing-0 text-left type-numeric"
            data-density={tableDensity}
            data-column-count={visibleColumnCount}
            style={{ minWidth: tableMinimumWidth }}
          >
            <thead className="type-table-header border-b-2 border-border bg-[var(--table-header-surface)] text-foreground align-middle text-center">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const align = columnAlign(header.column.id);
                    const meta = header.column.columnDef.meta as any;
                    const sortedIcon =
                      {
                        asc: <ArrowUp className="h-2 w-2 shrink-0" />,
                        desc: <ArrowDown className="h-2 w-2 shrink-0" />,
                      }[header.column.getIsSorted() as string] ??
                      (header.column.getCanSort() ? (
                        <ArrowUpDown className="h-2 w-2 shrink-0 opacity-70" />
                      ) : null);
                    const sortIndex = sorting.findIndex((item) => item.id === header.column.id);
                    return (
                      <th
                        key={header.id}
                        data-column-id={header.column.id}
                        className={cn(
                          "whitespace-normal border-b-2 border-border py-1 align-middle text-center leading-tight",
                          tableDensity === "compact" ? "px-1.5" : "responsive-table-cell-x",
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
                              header.column.getCanSort()
                                ? "cursor-pointer select-none hover:text-foreground transition-colors"
                                : "",
                            )}
                            title={
                              header.column.getCanSort()
                                ? "Click to add or cycle this column in the multi-column sort order."
                                : undefined
                            }
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            <span
                              className={cn(
                                "min-w-0 break-words leading-tight",
                                header.column.id === "tier" && "whitespace-nowrap break-normal",
                              )}
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                            </span>
                            {sortedIcon}
                            {sortIndex >= 0 && sorting.length > 1 && (
                              <span className="ml-0.5 rounded-full bg-primary/15 px-1 type-label font-semibold leading-4 text-primary">
                                {sortIndex + 1}
                              </span>
                            )}
                          </div>
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {visibleRows.length ? (
                visibleRows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn(
                      "bg-[var(--paper-raised)] transition-colors duration-75 hover:bg-primary/10",
                      getRowClassName?.(row.original) ?? "",
                    )}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const align = columnAlign(cell.column.id);
                      const meta = cell.column.columnDef.meta as any;
                      return (
                        <td
                          key={cell.id}
                          data-column-id={cell.column.id}
                          className={cn(
                            "min-w-0 overflow-hidden border-b border-border/55 align-middle",
                            tableDensity === "compact"
                              ? "px-1.5 py-1"
                              : "responsive-table-cell-x responsive-table-cell-y",
                            align === "center" ? "text-center" : "text-left",
                            defaultColumnClass(cell.column.id),
                            meta?.cellClassName,
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="h-24 text-center text-muted-foreground font-medium"
                  >
                    No results found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="data-table-footer flex min-h-11 flex-wrap items-center justify-end gap-2 border-t border-border/60 bg-card px-2 py-2 text-xs font-medium text-muted-foreground">
          <span>
            {serverPaginated
              ? `Showing ${rangeStart}-${rangeEnd} of ${shortCount(returnedCount)} ${rowLabel}`
              : paginated
                ? `Showing ${clientPagination.pageIndex * clientPagination.pageSize + 1}-${Math.min((clientPagination.pageIndex + 1) * clientPagination.pageSize, allFilteredRows.length)} of ${allFilteredRows.length} row(s)`
                : `Showing ${visibleRows.length} of ${allFilteredRows.length} row(s)`}
          </span>
          {serverPaginated && onPerPageChange && (
            <PageSizeSelect
              value={effectivePageSize}
              onValueChange={(nextPageSize) => {
                persistPageSize(nextPageSize);
                onPerPageChange(nextPageSize);
              }}
              showPageSuffix
            />
          )}
          {serverPaginated && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={!hasPrevious}
                onClick={() => onPageChange?.(Math.max(1, page - 1))}
                className="paper-inset rounded-lg px-2.5 py-1 font-semibold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
              >
                Previous
              </button>
              <span className="px-1 font-semibold text-foreground">Page {page}</span>
              <button
                type="button"
                disabled={!hasNext}
                onClick={() => onPageChange?.(page + 1)}
                className="paper-inset rounded-lg px-2.5 py-1 font-semibold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
              >
                Next
              </button>
            </div>
          )}
          {!serverPaginated && paginated && (
            <>
              <PageSizeSelect
                value={clientPagination.pageSize}
                onValueChange={(nextPageSize) => {
                  persistPageSize(nextPageSize);
                  setClientPagination({ pageIndex: 0, pageSize: nextPageSize });
                }}
                showPageSuffix
              />
              <button
                type="button"
                disabled={clientPage <= 1}
                onClick={() =>
                  setClientPagination((current) => ({
                    ...current,
                    pageIndex: Math.max(0, current.pageIndex - 1),
                  }))
                }
                className="paper-inset rounded-lg px-2.5 py-1 font-semibold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
              >
                Previous
              </button>
              <span className="px-1 font-semibold text-foreground">Page {clientPage}</span>
              <button
                type="button"
                disabled={clientPage >= clientPageCount}
                onClick={() =>
                  setClientPagination((current) => ({
                    ...current,
                    pageIndex: Math.min(clientPageCount - 1, current.pageIndex + 1),
                  }))
                }
                className="paper-inset rounded-lg px-2.5 py-1 font-semibold text-foreground hover:border-primary/30 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
              >
                Next
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
