import { TriangleAlert } from "lucide-react"
import { runtimeConfig } from "@/lib/runtime-config"

export function EnvironmentBanner({ environment = runtimeConfig.environment }: { environment?: string }) {
  const name = (environment || "unknown").trim().toLowerCase()
  if (name === "production" || name === "prod") return null
  return (
    <div role="status" className="badge-warning relative z-30 flex shrink-0 items-center justify-center gap-2 border-b px-3 py-1 text-sm">
      <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="break-words"><strong>{name.toUpperCase()}</strong> environment. Not for production clinical use.</span>
    </div>
  )
}
