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
    <button
      type="button"
      onClick={() => exportCsv.mutate()}
      disabled={exportCsv.isPending}
      className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
      title={exportCsv.error instanceof Error ? exportCsv.error.message : "Download backend-generated CSV"}
    >
      {exportCsv.isPending ? <icon.activity className="h-4 w-4 animate-spin" /> : <icon.download className="h-4 w-4" />}
      {label}
    </button>
  )
}
