import type { ReactNode } from "react"
import { CircleOff } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { type ApplicationModuleKey, useApplicationModules } from "@/lib/app-module-state"

export function ApplicationModuleBoundary({
  moduleKey,
  children,
}: {
  moduleKey: ApplicationModuleKey
  children: ReactNode
}) {
  const modules = useApplicationModules()
  if (modules.isLoading) return <AppLoader label="Checking module availability" />
  const definition = modules.data?.modules?.[moduleKey]
  if (definition?.enabled === false) {
    return (
      <section className="surface-panel mx-auto mt-6 max-w-2xl p-6 text-center">
        <CircleOff className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <h1 className="text-xl font-bold">{definition.label} is unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">{definition.description}</p>
        <p className="mt-3 text-xs text-muted-foreground">
          An application administrator has disabled this module. API requests for it return HTTP 503.
        </p>
      </section>
    )
  }
  return <>{children}</>
}
