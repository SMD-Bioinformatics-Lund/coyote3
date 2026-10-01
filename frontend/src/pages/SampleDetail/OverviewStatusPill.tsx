import type { ReactNode } from "react";


export function StatusPill({ children, tone = "muted" }: { children: ReactNode; tone?: "blue" | "green" | "yellow" | "red" | "muted" }) {
  const tones = {
    blue: "badge-info",
    green: "badge-success",
    yellow: "badge-warning",
    red: "badge-danger",
    muted: "badge-neutral",
  }
  return <span className={`type-badge inline-flex min-h-5 items-center rounded-md border px-2 py-0.5 ${tones[tone]}`}>{children}</span>
}
