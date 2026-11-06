import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRef } from "react"
import type { ReportType } from "@/components/reports/report-snapshot"
import { api, ApiClientError } from "@/lib/api"
import type { ReportPreviewPayload } from "@/lib/generated"
import { downloadBlob } from "@/lib/browser-download"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { validateReportPdf } from "@/lib/report-pdf"

async function loadPreviewPdf(endpoint: string, signal?: AbortSignal): Promise<Blob> {
  const response = await api.getBlob(endpoint, {
    signal, credentials: "same-origin", cache: "no-store", errorNotice: "inline",
    headers: { Accept: "application/pdf" },
  })
  return validateReportPdf(response.data)
}

/** Own preview requests, PDF reuse, save preconditions and report mutation feedback. */
export function useReportPreview({ sampleId, reportType, includeSnapshot, pdfEnabled, onSaved, reportFormat = "modern" }: {
  sampleId: string
  reportType: ReportType
  includeSnapshot: boolean
  pdfEnabled: boolean
  onSaved: () => void
  reportFormat?: "modern" | "legacy"
}) {
  const queryClient = useQueryClient()
  const activeScope = useRef("")
  activeScope.current = JSON.stringify([sampleId, reportType, reportFormat])
  const requestContext = () => ({ sampleId, reportType, sampleName: data?.sample?.name || sampleId,
    scope: activeScope.current })
  const reportEndpoint = `/samples/${encodeURIComponent(sampleId)}/reports/${reportType}`
  const pdfEndpoint = `${reportEndpoint}/preview/pdf?include_snapshot=${includeSnapshot}&format=${reportFormat}`

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["report-preview", sampleId, reportType, includeSnapshot, reportFormat],
    queryFn: () =>
      api
        .get<ReportPreviewPayload>(`${reportEndpoint}/preview?include_snapshot=${includeSnapshot}&save=false&format=${reportFormat}`)
        .then((response) => response.data),
    retry: false,
    refetchOnMount: "always",
  })

  const hasRenderedHtml = Boolean(data?.meta?.template_status?.has_html && data?.report?.html)
  const pdfPreview = useQuery({
    queryKey: ["report-pdf-preview", sampleId, reportType, includeSnapshot, data?.meta?.preview_fingerprint, reportFormat],
    queryFn: ({ signal }) => loadPreviewPdf(pdfEndpoint, signal),
    enabled: hasRenderedHtml && pdfEnabled,
    retry: (attempt, failure) => attempt < 1 && failure instanceof ApiClientError
      && (failure.status === 0 || (failure.status ?? 0) >= 500),
    gcTime: 0,
    staleTime: Infinity,
  })

  const saveReport = useMutation({
    onMutate: requestContext,
    mutationFn: () => api.post(reportEndpoint, {
      preview_fingerprint: data?.meta?.preview_fingerprint,
      report_format: reportFormat,
    }),
    onSuccess: (_response, _variables, context) => {
      const { sampleId, reportType, sampleName } = context
      if (activeScope.current === context.scope) onSaved()
      queryClient.invalidateQueries({ queryKey: ["report-preview", sampleId, reportType] })
      queryClient.invalidateQueries({ queryKey: ["samples"] })
      queryClient.invalidateQueries({ queryKey: ["sample-navigation-counts"] })
      notifySuccess("Report saved", `${reportType.toUpperCase()} report was saved for ${sampleName}.`, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()}`,
        sampleName,
      })
    },
    onError: (mutationError, _variables, context) => {
      const { sampleId, reportType, sampleName } = context ?? requestContext()
      notifyActionError("Unable to save report", mutationError, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()}`,
        sampleName,
      })
    },
  })

  const downloadPreviewPdf = useMutation({
    onMutate: requestContext,
    mutationFn: async () => {
      const blob = pdfPreview.data ?? await loadPreviewPdf(pdfEndpoint)
      downloadBlob(blob, `${data?.sample?.name || sampleId}_${reportType}_preview.pdf`)
    },
    onSuccess: (_response, _variables, context) => {
      const { sampleId, reportType, sampleName } = context
      notifySuccess(
        "PDF generated",
        `The temporary ${reportType.toUpperCase()} report preview PDF for ${sampleName} was downloaded.`,
        "Reports",
        { type: "report", id: sampleId, name: `${sampleName} ${reportType.toUpperCase()} preview`, sampleName },
      )
    },
    onError: (mutationError, _variables, context) => {
      const { sampleId, reportType, sampleName } = context ?? requestContext()
      notifyActionError("Unable to generate PDF", mutationError, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()} preview`,
        sampleName,
      })
    },
  })

  return { data, isLoading, error, refetch, hasRenderedHtml, pdfPreview, saveReport, downloadPreviewPdf }
}
