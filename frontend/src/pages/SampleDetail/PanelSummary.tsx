import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { normalizePanelEntries } from "./overview-data";

export function PanelSummary({ sample, context }: { sample: any; context?: any }) {
  const [open, setOpen] = useState(false)
  const entries = normalizePanelEntries(context, sample)
  const isFusion = entries.length > 0 && entries.every((entry: any) => entry.target === "FUSION")
  const title = isFusion ? "Fusion List(s)" : "Gene Panel(s)"
  const emptyText = isFusion ? "No fusion list filters applied" : "No genelist filters applied"

  return (
    <section className="glass-panel overflow-hidden rounded-xl border border-border/80 bg-card/85 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 border-b border-border/70 bg-muted/45 px-4 py-3 text-left transition-colors duration-100 hover:bg-primary/8 dark:bg-muted/25 dark:hover:bg-primary/12"
      >
        <div className="min-w-0">
          <h2 className="type-section-title text-foreground">{title}</h2>
          <p className="type-meta mt-0.5 text-muted-foreground">
            {entries.length ? `${entries.length} selected list${entries.length === 1 ? "" : "s"}` : emptyText}
          </p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />}
      </button>

      <div className="px-4 py-3 text-sm font-medium">
        {entries.length ? (
          <div className="flex flex-wrap gap-1.5">
            {entries.map((raw: any) => {
              const covered = raw?.covered || []
              const genes = raw?.genes || []
              const name = raw?.name || raw?.id
              return (
                <span
                  key={`${raw?.target || "GENE"}-${raw?.id || name}`}
                  className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-bold shadow-sm transition-colors duration-100 ${
                    raw?.is_active === false
                      ? "border-warn/35 bg-warn/10 text-warn hover:bg-warn/10"
                      : raw?.adhoc
                        ? "border-primary/25 bg-primary/8 text-primary hover:bg-primary/8"
                        : "border-genelist/30 bg-genelist/10 text-genelist hover:bg-genelist/10"
                  }`}
                >
                  <span className="font-semibold uppercase">{raw?.target || "GENE"}</span>
                  <span className="text-foreground">{name}</span>
                  {raw?.adhoc ? <span className="rounded bg-primary/10 px-1 type-label uppercase text-primary">Ad hoc</span> : null}
                  <span className="text-muted-foreground">
                    {Number(raw?.covered_count ?? covered.length)} / {Number(raw?.gene_count ?? genes.length)} covered
                  </span>
                </span>
              )
            })}
          </div>
        ) : (
          <span className="font-bold text-muted-foreground">{emptyText}</span>
        )}
      </div>

      {open && entries.length > 0 && (
        <div className="space-y-2 px-3 pb-3">
          {entries.map((raw: any) => {
            const covered = raw?.covered || []
            const genes = raw?.genes || []
            const uncovered = raw?.uncovered || []
            const name = raw?.name || raw?.id
            return (
              <div key={`${raw?.target || "GENE"}-${raw?.id || name}`} className="rounded-lg border border-border/80 bg-background/70 p-3 shadow-sm">
                <p className={raw?.is_active === false ? "text-sm font-bold text-warn" : "text-sm font-bold text-foreground"}>
                  <span className="uppercase text-muted-foreground">{raw?.target || "GENE"}</span>: {name} {raw?.adhoc ? <span className="rounded bg-primary/10 px-1.5 py-0.5 type-label uppercase text-primary">Ad hoc</span> : null}
                  <span className="ml-2 text-muted-foreground">
                    {Number(raw?.covered_count ?? covered.length)} of {Number(raw?.gene_count ?? genes.length)} gene(s) covered
                  </span>
                  {raw?.is_active === false ? <span className="ml-2 text-warn">Inactive list, filter not applied.</span> : null}
                </p>
                {genes.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                    {genes.map((gene: string) => (
                      <span
                        key={gene}
                        title={covered.includes(gene) ? "This gene is covered in the panel" : "This gene is not covered in the panel"}
                        className={covered.includes(gene) ? "rounded-md border border-pass/30 bg-pass/10 px-1.5 py-0.5 font-semibold text-pass" : "rounded-md border border-warn/35 bg-warn/10 px-1.5 py-0.5 font-semibold text-warn"}
                      >
                        {gene}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {Number(raw?.covered_count || 0)} covered gene(s)
                    {uncovered.length ? `, ${uncovered.length} outside assay coverage` : ""}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
