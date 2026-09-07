import { useQuery } from "@tanstack/react-query"
import { Suspense, lazy } from "react"

import { SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { KnowledgebaseOnline } from "@/components/knowledgebase/KnowledgebaseOnline"
import {
  KnowledgebaseStatus,
  type KnowledgebaseStatusPayload,
} from "@/components/knowledgebase/KnowledgebaseStatus"
import { api } from "@/lib/api"

const CancerGeneCensusChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.CancerGeneCensusChart })))
const KnowledgebaseStatisticsCharts = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.KnowledgebaseStatisticsCharts })))

function ChartFallback() {
  return <AppLoader label="Loading Cancer Gene Census chart" />
}

export function KnowledgebaseDetails() {
  const statusQuery = useQuery({
    queryKey: ["knowledgebase-status"],
    queryFn: () => api.get<KnowledgebaseStatusPayload>("/public/knowledgebases/status").then((response) => response.data),
    staleTime: 5 * 60 * 1000,
  })
  const censusQuery = useQuery({
    queryKey: ["cancer-gene-census-summary"],
    queryFn: () => api.get("/knowledgebases/cosmic/cancer-gene-census/summary").then((response) => response.data),
    staleTime: 5 * 60 * 1000,
  })
  const statisticsQuery = useQuery({
    queryKey: ["knowledgebase-statistics"],
    queryFn: () => api.get("/knowledgebases/statistics").then((response) => response.data),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <PageShell
      eyebrow="Reference intelligence"
      title="Knowledgebase Details"
      description="Installed reference sources, release provenance, indexed content, and aggregate knowledgebase coverage."
    >
      <SurfacePanel
        className="dashboard-panel dashboard-panel--teal"
        title="Knowledgebases online"
        description="Top-level sources currently installed or configured for interpretation."
      >
        {statusQuery.isLoading ? (
          <AppLoader label="Loading knowledgebase status" />
        ) : (
          <KnowledgebaseOnline payload={statusQuery.data} showDetailsLink={false} />
        )}
      </SurfacePanel>

      {statisticsQuery.data?.sources?.some((source: { available?: boolean }) => source.available) ? (
        <SurfacePanel
          className="dashboard-panel dashboard-panel--blue"
          title="Reference coverage"
          description="Aggregate gene and transcript coverage from installed public knowledgebases. Rings represent source-defined categories or explicitly labelled feature coverage."
        >
          <Suspense fallback={<ChartFallback />}>
            <KnowledgebaseStatisticsCharts sources={statisticsQuery.data.sources} />
          </Suspense>
        </SurfacePanel>
      ) : null}

      {censusQuery.data?.available ? (
        <SurfacePanel
          className="dashboard-panel dashboard-panel--rose"
          title="Cancer Gene Census"
          description="Gene tiers, origin scope, roles in cancer, mutation types, and hallmark coverage."
        >
          <Suspense fallback={<ChartFallback />}>
            <CancerGeneCensusChart data={censusQuery.data} />
          </Suspense>
        </SurfacePanel>
      ) : null}

      <SurfacePanel
        className="dashboard-panel dashboard-panel--amber"
        title="Installed products"
        description="Product-level releases, collection counts, and indexed record totals."
      >
        {statusQuery.isLoading ? (
          <AppLoader label="Loading installed products" />
        ) : (
          <KnowledgebaseStatus payload={statusQuery.data} />
        )}
      </SurfacePanel>
    </PageShell>
  )
}
