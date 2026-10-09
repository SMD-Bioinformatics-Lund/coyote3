import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { AdminHomeLink } from "./AdminHomeLink"

type Plan = {
  configuration: Record<string, number>
  configuration_installed: boolean
  samples: { key: string; name: string; installed: boolean }[]
}

export default function DemoInstallationPage() {
  const [confirmed, setConfirmed] = useState(false)
  const [progress, setProgress] = useState("")
  const plan = useQuery({
    queryKey: ["demo-installation"],
    queryFn: () => api.get<Plan>("/admin/demo-installation").then((response) => response.data),
    retry: false,
  })
  const install = useMutation({
    mutationFn: async (samples: boolean) => {
      if (!plan.data || !confirmed) return
      if (!plan.data.configuration_installed) {
        setProgress("Installing demonstration configuration…")
        await api.post("/admin/demo-installation/configuration")
      }
      if (samples) {
        for (const sample of plan.data.samples.filter((item) => !item.installed)) {
          setProgress(`Installing ${sample.name}…`)
          await api.post(`/admin/demo-installation/samples/${encodeURIComponent(sample.key)}`)
        }
      }
      setProgress(samples ? "Demo configuration and samples are installed." : "Demo configuration is installed.")
    },
    onError: () => setProgress("Installation stopped. Completed items are preserved; refresh the status before retrying."),
    onSettled: () => { void plan.refetch() },
  })
  return (
    <PageShell eyebrow="Administration" title="Demo installation" description="Install the packaged synthetic workflow bundle in this deployment." actions={<AdminHomeLink />}>
      <section className="surface-panel space-y-4 p-4">
        <p className="type-body-sm">Includes demonstration assays, testing profiles, gene lists, a subpanel and report-rule drafts. Sample files are processed through normal ingest. Existing records are preserved; report rules are not published.</p>
        <p className="type-body-sm text-muted-foreground">These artificial findings are for training and validation. They are not clinical evidence. No accounts, external knowledgebases, BAM files or saved clinical reports are installed. Sample visibility requires access to the testing environment and the relevant assays.</p>
        {plan.isLoading && <p role="status">Loading demo installation status…</p>}
        {plan.error && <p role="alert">Unable to load installation status. <Button variant="outline" onClick={() => void plan.refetch()}>Retry</Button></p>}
        {plan.data && <>
          <dl className="grid gap-3 sm:grid-cols-3">
            {Object.entries(plan.data.configuration).map(([name, count]) => <div key={name} className="rounded-lg border border-border p-3"><dt className="type-meta text-muted-foreground">{name.replaceAll("_", " ")}</dt><dd className="type-body-sm font-semibold">{count}</dd></div>)}
          </dl>
          <label className="flex items-start gap-2 type-body-sm"><input type="checkbox" checked={confirmed} disabled={install.isPending} onChange={(event) => setConfirmed(event.target.checked)} />I understand this installs synthetic testing data in the current deployment.</label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!confirmed || install.isPending || plan.data.configuration_installed} onClick={() => install.mutate(false)}>Install configuration only</Button>
            <Button disabled={!confirmed || install.isPending || (plan.data.configuration_installed && plan.data.samples.every((sample) => sample.installed))} onClick={() => install.mutate(true)}>Install configuration and samples</Button>
          </div>
          <ul className="divide-y divide-border">{plan.data.samples.map((sample) => <li key={sample.key} className="flex flex-wrap justify-between gap-2 py-2 type-body-sm"><span>{sample.name}</span><span className="text-muted-foreground">{sample.installed ? "Present" : "Not installed"}</span></li>)}</ul>
        </>}
        {progress && <p role="status" className="type-body-sm">{progress}</p>}
        {install.error && <p role="alert" className="type-body-sm text-destructive">{install.error instanceof Error ? install.error.message : "Unable to install demonstration data."}</p>}
      </section>
    </PageShell>
  )
}
