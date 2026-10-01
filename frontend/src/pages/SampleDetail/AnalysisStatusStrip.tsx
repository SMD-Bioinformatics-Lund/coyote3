import { shortCount } from "@/lib/detail-formatters";
import { SettingsCard } from "@/pages/SampleDetail/SampleGeneSettings";
import { analysisStatusItems } from "./overview-data";
import { StatusPill } from "./OverviewStatusPill";

export function AnalysisStatusStrip({ sample, context }: { sample: any; context?: any }) {
  const items = analysisStatusItems(sample, context)
  if (!items.length) return null

  return (
    <SettingsCard title="Analysis Status" tone="border-t-primary">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {items.map((item) => {
          const tone = item.present ? "green" : "red"
          const filteredText = item.filtered > 0 ? `${shortCount(item.filtered)} filtered` : "filter on demand"
          const rawText = item.raw > 0 ? `${shortCount(item.raw)} raw` : item.present ? "file present" : "missing"
          return (
            <div key={item.key} className="rounded-xl border border-border bg-background/70 p-2">
              <div className="flex items-start justify-between gap-2">
                <h3 className="type-label text-foreground">{item.label}</h3>
                <StatusPill tone={tone}>{item.present ? "Ready" : "Not available"}</StatusPill>
              </div>
              <p className="type-meta mt-2 text-foreground/80">{rawText}</p>
              <p className="type-meta text-muted-foreground">{filteredText}</p>
            </div>
          )
        })}
      </div>
    </SettingsCard>
  )
}
