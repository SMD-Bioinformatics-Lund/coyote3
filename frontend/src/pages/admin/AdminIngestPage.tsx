import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess, notifyWarning } from "@/lib/notifications"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  Activity,
  Database,
  FileUp
} from "lucide-react"
import { useEffect, useRef, useState } from "react"


import { ModuleNotice } from "@/components/admin/ModuleNotice"

export function AdminIngestPage() {
  const [yamlFile, setYamlFile] = useState<File | null>(null)
  const [dataArchive, setDataArchive] = useState<File | null>(null)
  const [updateExisting, setUpdateExisting] = useState(false)
  const [increment, setIncrement] = useState(false)
  const [taskId, setTaskId] = useState("")
  const notifiedFailure = useRef("")
  const taskStatus = useQuery({
    queryKey: ["internal-task", taskId],
    enabled: Boolean(taskId),
    queryFn: () => api.get(`/internal/tasks/${taskId}`).then((res) => res.data),
    refetchInterval: (query) => query.state.data?.ready ? false : 2000,
    retry: false,
  })
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!yamlFile) throw new Error("Select a coyote3 YAML manifest before submitting.")
      const formData = new FormData()
      formData.append("yaml_file", yamlFile)
      if (dataArchive) formData.append("data_archive", dataArchive)
      formData.append("update_existing", String(updateExisting))
      formData.append("increment", String(increment))
      return api.post("/internal/ingest/sample-bundle/upload/async", formData).then((res) => res.data)
    },
    onSuccess: (payload) => {
      setTaskId(String(payload.task_id || ""))
      for (const warning of payload.warnings || []) {
        notifyWarning("Ingest file ignored", String(warning), "Ingest workspace", {
          type: "ingest", id: String(payload.task_id || ""),
        })
      }
      notifySuccess("Ingest queued", `${yamlFile?.name || "Sample bundle"} was submitted to the ingest worker.`, "Ingest workspace", {
        type: "ingest",
        id: String(payload.task_id || ""),
        name: yamlFile?.name,
      })
    },
    onError: (error) => {
      notifyActionError("Unable to queue ingest", error, "Ingest workspace", {
        type: "ingest",
        name: yamlFile?.name || "sample bundle",
      })
    },
  })

  useEffect(() => {
    if (!taskId || taskStatus.data?.state !== "FAILURE" || notifiedFailure.current === taskId) return
    notifiedFailure.current = taskId
    notifyActionError("Ingest failed", new Error(String(taskStatus.data.error || "Ingestion failed")), "Ingest workspace", {
      type: "ingest",
      id: taskId,
    })
  }, [taskId, taskStatus.data])

  return (
    <PageShell eyebrow="Admin" title="Ingest Workspace" description="Validate and enqueue sample-bundle ingestion through the internal API and Celery ingest workers.">
      <div className="grid gap-3 xl:grid-cols-2">
        <section className="surface-panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <FileUp className="h-5 w-5 text-dna" />
            <h2 className="text-lg font-bold">Sample Bundle Upload</h2>
          </div>
          <div className="space-y-3">
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">YAML manifest</span>
              <input
                type="file"
                accept=".yaml,.yml"
                onChange={(event) => setYamlFile(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Referenced data archive</span>
              <input
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => setDataArchive(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
              <span className="block text-xs text-muted-foreground">
                Optional when the manifest paths are already readable. Otherwise upload one ZIP containing every declared data file.
              </span>
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="flex items-center gap-2 rounded-lg border border-border bg-background/70 px-3 py-2 text-sm font-semibold">
                <input type="checkbox" checked={updateExisting} onChange={(event) => setUpdateExisting(event.target.checked)} />
                Update existing sample
              </label>
              <label className="flex items-center gap-2 rounded-lg border border-border bg-background/70 px-3 py-2 text-sm font-semibold">
                <input type="checkbox" checked={increment} onChange={(event) => setIncrement(event.target.checked)} />
                Increment sample name
              </label>
            </div>
            <button
              type="button"
              onClick={() => uploadMutation.mutate()}
              disabled={!yamlFile || uploadMutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
            >
              {uploadMutation.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
              Queue ingest
            </button>
          </div>
        </section>
        <section className="surface-panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <Database className="h-5 w-5 text-rna" />
            <h2 className="text-lg font-bold">Worker Task</h2>
          </div>
          {taskId ? (
            <div className="space-y-3">
              <div className="rounded-xl border border-border bg-background/70 p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Task ID</p>
                <p className="break-all text-sm">{taskId}</p>
              </div>
              {taskStatus.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground"><Activity className="h-4 w-4 animate-spin" /> Checking worker state...</div>
              ) : taskStatus.error ? (
                <ModuleNotice>{taskStatus.error instanceof Error ? taskStatus.error.message : "Unable to read task state."}</ModuleNotice>
              ) : (
                <div className="space-y-2">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <TaskMetric label="State" value={taskStatus.data?.state || "-"} />
                    <TaskMetric label="Ready" value={taskStatus.data?.ready ? "yes" : "no"} />
                    <TaskMetric label="Successful" value={taskStatus.data?.successful === null || taskStatus.data?.successful === undefined ? "-" : taskStatus.data?.successful ? "yes" : "no"} />
                  </div>
                  {taskStatus.data?.error && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                      {String(taskStatus.data.error)}
                    </div>
                  )}
                  {taskStatus.data?.result && (
                    <div className="rounded-lg border border-pass/30 bg-pass/10 p-3 text-sm">
                      <p className="font-bold text-pass">Ingest result</p>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(taskStatus.data.result, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Submit a YAML manifest to enqueue an ingest task. The worker status appears here until the task completes.
            </p>
          )}
        </section>
      </div>
    </PageShell>
  )
}

function TaskMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background/70 p-3">
      <p className="type-meta font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  )
}
