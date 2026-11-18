// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { LoadingIndicator } from "@/components/ui/loading-indicator"
import { Button } from "@/components/ui/button"
import { useMutation } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { api } from "@/lib/api"
import { downloadText } from "@/lib/browser-download"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

function saveCsv(payload: any, fallbackFilename: string) {
  downloadText(
    payload?.content || "",
    payload?.filename || fallbackFilename,
    "text/csv;charset=utf-8",
  )
}

export function ServerCsvButton({
  endpoint,
  fallbackFilename,
  label = "Export to CSV",
}: {
  endpoint: string
  fallbackFilename: string
  label?: string
}) {
  const exportCsv = useMutation({
    mutationFn: () => api.get(endpoint).then((res) => res.data),
    onSuccess: (payload) => {
      saveCsv(payload, fallbackFilename)
      notifySuccess("CSV exported", `${payload?.filename || fallbackFilename} was downloaded.`, "Export")
    },
    onError: (error) => {
      notifyActionError("Unable to export CSV", error, "Export")
    },
  })

  return (
    <Button variant="outline" size="sm"
      type="button"
      onClick={() => exportCsv.mutate()}
      disabled={exportCsv.isPending}
      title={exportCsv.error instanceof Error ? exportCsv.error.message : "Download backend-generated CSV"}
    >
      {exportCsv.isPending ? <LoadingIndicator className="h-4 w-4" /> : <icon.download className="h-4 w-4" />}
      {label}
    </Button>
  )
}
