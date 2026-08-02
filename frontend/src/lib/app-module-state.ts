import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export type ApplicationModuleKey =
  | "dna_analysis"
  | "rna_analysis"
  | "reports"
  | "variant_search"
  | "knowledgebases"
  | "ingest_workspace"
  | "assay_catalog"

export type ApplicationModuleState = {
  enabled: boolean
  label: string
  description: string
}

export type ApplicationModulesPayload = {
  modules: Partial<Record<ApplicationModuleKey, ApplicationModuleState>>
}

export function useApplicationModules() {
  return useQuery<ApplicationModulesPayload>({
    queryKey: ["application-modules"],
    queryFn: () => api.get<ApplicationModulesPayload>("/public/modules").then((response) => response.data),
    staleTime: 15_000,
    retry: false,
  })
}

export function moduleIsEnabled(
  payload: ApplicationModulesPayload | undefined,
  key: ApplicationModuleKey,
) {
  return payload?.modules?.[key]?.enabled !== false
}
