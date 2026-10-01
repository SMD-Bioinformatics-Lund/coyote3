import { TierBadge } from "@/lib/variant-ui";
import { percent } from "./cohort-formatters";

export function CurrentAndPriorTiers({ current, prior }: { current: number[]; prior: number[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {current.map((tier) => (
        <span
          key={`current-${tier}`}
          className="inline-flex rounded-full ring-2 ring-foreground/20 ring-offset-1 ring-offset-card"
          aria-label={`Current tier ${tier}`}
        >
          <TierBadge tier={tier} />
        </span>
      ))}
      {prior.length > 0 && (
        <span
          className="flex items-center gap-1 border-l border-border pl-2"
          aria-label="Prior tiers"
        >
          {prior.map((tier) => (
            <span key={`prior-${tier}`} className="inline-flex opacity-60">
              <TierBadge tier={tier} />
            </span>
          ))}
        </span>
      )}
    </div>
  );
}

export function PrevalenceBar({ value }: { value: number | null }) {
  const width = Math.max(0, Math.min(100, value || 0));
  return (
    <div
      className="h-2 overflow-hidden rounded-full bg-muted"
      aria-label={`Prevalence ${percent(value)}`}
    >
      <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
    </div>
  );
}

export function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="metric-card rounded-xl">
      <p className="type-label text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      <p className="type-caption mt-1 text-muted-foreground">{detail}</p>
    </div>
  );
}
