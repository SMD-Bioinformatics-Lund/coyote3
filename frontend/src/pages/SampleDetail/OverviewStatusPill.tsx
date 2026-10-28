import type { ReactNode } from "react";
import { configuredValueClasses } from "@/lib/badge-colors";


export function StatusPill({ children, tone = "muted" }: { children: ReactNode; tone?: "blue" | "green" | "yellow" | "red" | "muted" }) {
  const tones = {
    blue: "badge-tone-blue",
    green: "badge-tone-green",
    yellow: "badge-tone-yellow",
    red: "badge-tone-red",
    muted: "badge-tone-muted",
  }
  const valueClass = typeof children === "string"
    ? configuredValueClasses[children.toLowerCase()]
    : undefined
  return <span className={`type-badge inline-flex min-h-5 items-center rounded-md border px-2 py-0.5 ${valueClass || tones[tone]}`}>{children}</span>
}
