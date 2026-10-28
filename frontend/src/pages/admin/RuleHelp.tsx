import { icon } from "@/lib/assets"
import { AppTooltip } from "@/components/ui/app-tooltip"

export function RuleHelp({ label, children }: { label: string; children: string }) {
  return <AppTooltip label={label} content={children} context="Report builder guidance" persistOnClick>
    <button type="button" aria-label={`Help: ${label}`} className="inline-flex shrink-0 items-center justify-center rounded-full p-1 text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><icon.circleHelp aria-hidden="true" className="size-4" /></button>
  </AppTooltip>
}
