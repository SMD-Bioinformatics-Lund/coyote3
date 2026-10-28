import { icon } from "@/lib/assets"
import { AppTooltip } from "@/components/ui/app-tooltip"

export type SampleDataSegment = {
  label: string
  value?: string
  title?: string
  className: string
}

export function SampleDataStatus({ segments }: { segments: SampleDataSegment[] }) {
  if (!segments.length) return <span className="text-muted-foreground">-</span>

  const rows = segments.map((segment) => ({
    ...segment,
    available: segment.className === "matte-badge-pass",
  }))
  const availableCount = rows.filter((row) => row.available).length
  const summary = `${availableCount} of ${rows.length} data types available`
  const complete = availableCount === rows.length
  const StatusIcon = complete ? icon.check : availableCount === 0 ? icon.x : icon.triangleAlert
  const statusClass = complete ? "matte-badge-pass"
    : availableCount === 0 ? "matte-badge-fail" : "matte-badge-warn"
  const description = rows.map((row) =>
    `${row.label}: ${row.available ? "Available" : "Not available"}${row.value === undefined ? "" : ` (${row.value})`}`,
  ).join("; ")

  return (
    <AppTooltip context="Sample data" content={summary} label={summary}
      tone={availableCount === rows.length ? "success" : availableCount === 0 ? "danger" : "warning"}
      persistOnClick details={
        <dl className="mt-2 space-y-1 type-meta leading-relaxed text-foreground/75">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4">
              <dt className="font-semibold text-foreground">{row.label}</dt>
              <dd className="type-meta flex items-center gap-1 tabular-nums">
                {row.available ? (
                  row.value !== undefined ? <span className="text-foreground">{row.value}</span> : (
                    <>
                      <icon.check className="h-3 w-3 text-pass" aria-hidden="true" />
                      <span className="sr-only">Available</span>
                    </>
                  )
                ) : (
                  <>
                    <icon.x className="h-3 w-3 text-fail" aria-hidden="true" />
                    <span className="sr-only">Not available</span>
                  </>
                )}
              </dd>
            </div>
          ))}
        </dl>
      }>
      <button type="button" aria-label={`${summary}. ${description}`}
        className={`inline-flex h-5 w-6 items-center justify-center rounded-full border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${statusClass}`}>
        <StatusIcon className="h-3 w-3" aria-hidden="true" />
      </button>
    </AppTooltip>
  )
}
