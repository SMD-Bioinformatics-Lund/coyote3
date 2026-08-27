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
  curation?: {
    tiering?: Partial<Record<TieringResourceKey, boolean>>
  }
}

export type TieringResourceKey = "small_variant" | "cnv" | "fusion" | "translocation"

const DEFAULT_TIERING_AVAILABILITY: Record<TieringResourceKey, boolean> = {
  small_variant: true,
  cnv: false,
  fusion: true,
  translocation: false,
}

export const APPLICATION_MODULES_QUERY_KEY = ["application-modules"] as const

export function useApplicationModules() {
  return useQuery<ApplicationModulesPayload>({
    queryKey: APPLICATION_MODULES_QUERY_KEY,
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

export function tieringIsEnabled(
  payload: ApplicationModulesPayload | undefined,
  resourceType: TieringResourceKey,
) {
  return payload?.curation?.tiering?.[resourceType]
    ?? DEFAULT_TIERING_AVAILABILITY[resourceType]
}
