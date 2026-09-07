import type { ColumnDef } from "@tanstack/react-table"

import { RowSelectionCheckbox } from "./RowSelectionCheckbox"

export function createRowSelectionColumn<TData>(): ColumnDef<TData> {
  return {
    id: "select",
    meta: {
      headerClassName: "w-8 min-w-8 max-w-8",
      cellClassName: "w-8 min-w-8 max-w-8",
    },
    header: ({ table }) => (
      <RowSelectionCheckbox
        checked={table.getIsAllPageRowsSelected()}
        indeterminate={table.getIsSomePageRowsSelected() && !table.getIsAllPageRowsSelected()}
        onChange={table.getToggleAllPageRowsSelectedHandler()}
        label="Select all rows on this page"
      />
    ),
    cell: ({ row }) => (
      <RowSelectionCheckbox
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        label="Select row"
      />
    ),
    enableSorting: false,
    size: 32,
    minSize: 32,
    maxSize: 32,
  }
}
