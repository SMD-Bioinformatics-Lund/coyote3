export type TooltipPosition = {
  left: number
  top: number
}

export type TooltipTone = "info" | "success" | "warning" | "danger" | "neutral"

export function tooltipToneClass(tone: string) {
  if (tone === "success" || tone === "pass") return "border-pass/45 text-pass"
  if (tone === "warning" || tone === "warn") return "border-warn/50 text-warn"
  if (tone === "danger" || tone === "fail") return "border-fail/45 text-fail"
  if (tone === "neutral") return "border-muted-foreground/35 text-muted-foreground"
  return "border-info/45 text-info"
}
