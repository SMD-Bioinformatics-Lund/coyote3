export type UiRouteAudit = {
  path: string
  page: string
  area: "clinical" | "public" | "admin" | "account" | "system"
  api: string[]
  dataUsed: string[]
  expectedFields?: string[]
  emptyState?: string
  errorState?: string
  notes?: string
}

export function routeExpectedFields(route: UiRouteAudit): string[] {
  return route.expectedFields?.length ? route.expectedFields : route.dataUsed
}

export function routeEmptyState(route: UiRouteAudit): string {
  return route.emptyState || "Shows an empty table or no-data message without throwing."
}

export function routeErrorState(route: UiRouteAudit): string {
  return route.errorState || "Shows a page-local error state and preserves navigation."
}

export const uiRouteRegistry: UiRouteAudit[] = [
  {
    path: "/",
    page: "Dashboard",
    area: "clinical",
    api: ["GET /dashboard/summary"],
    dataUsed: ["sample counts", "variant counts", "tier distribution", "assay profile summary", "resource capacity"],
  },
  {
    path: "/samples",
    page: "Samples",
    area: "clinical",
    api: ["GET /samples"],
    dataUsed: ["live_samples", "sample identity", "profile", "assay", "subpanel", "ingest_status", "time_added"],
  },
  {
    path: "/samples/:id",
    page: "SampleDetail",
    area: "clinical",
    api: [
      "GET /samples/:id/edit-context",
      "GET /samples/:id/small-variants",
      "GET /samples/:id/cnvs",
      "GET /samples/:id/fusions",
      "GET /samples/:id/translocations",
      "GET /coverage/samples/:id",
      "POST /samples/:id/comments",
      "PUT /samples/:id/filters",
    ],
    dataUsed: ["sample", "assay_config", "filters", "display_sections_data", "comments", "coverage payload", "report previews"],
  },
  {
    path: "/samples/:id/variant/:varId",
    page: "VariantDetail",
    area: "clinical",
    api: ["GET /samples/:id/small-variants/:varId", "POST /samples/:id/annotations"],
    dataUsed: ["variant", "sample_summary", "annotations", "classifications", "other sample observations", "comments"],
  },
  {
    path: "/samples/:id/cnv/:varId",
    page: "CNVDetail",
    area: "clinical",
    api: ["GET /samples/:id/cnvs/:varId"],
    dataUsed: ["cnv", "genes", "classifications", "artefact frequencies", "comments"],
  },
  {
    path: "/samples/:id/fusion/:varId",
    page: "FusionDetail",
    area: "clinical",
    api: ["GET /samples/:id/fusions/:varId"],
    dataUsed: ["fusion", "selected call", "classifications", "comments"],
  },
  {
    path: "/samples/:id/translocation/:varId",
    page: "TranslocationDetail",
    area: "clinical",
    api: ["GET /samples/:id/translocations/:varId"],
    dataUsed: ["translocation", "genes", "breakpoints", "classifications", "comments"],
  },
  {
    path: "/samples/:id/reports/:reportId",
    page: "SavedReportPage",
    area: "clinical",
    api: ["GET /samples/:id/reports/:reportId/html", "GET /samples/:id/reports/:reportId/download"],
    dataUsed: ["saved HTML report"],
  },
  {
    path: "/variants/search",
    page: "TieredVariantSearch",
    area: "clinical",
    api: ["GET /common/search/tiered_variants"],
    dataUsed: ["tiered variant rows", "sample and variant references"],
  },
  {
    path: "/reports",
    page: "ReportsPage",
    area: "clinical",
    api: ["GET /samples/:sampleId/reports/:reportType/preview", "POST /samples/:sampleId/reports/:reportType"],
    dataUsed: ["report context rows", "snapshot rows", "report generation status"],
  },
  {
    path: "/public",
    page: "PublicCatalog",
    area: "public",
    api: ["GET /public/assay-catalog/context", "GET /public/assay-catalog/genes.csv/context"],
    dataUsed: ["catalog panels", "gene list rows", "public navigation"],
  },
  {
    path: "/public/catalog",
    page: "PublicCatalog",
    area: "public",
    api: ["GET /public/assay-catalog/context", "GET /public/assay-catalog/genes.csv/context"],
    dataUsed: ["catalog panels", "gene list rows", "download CSV payload"],
  },
  {
    path: "/public/matrix",
    page: "PublicCatalogMatrix",
    area: "public",
    api: ["GET /public/assay-catalog-matrix/context"],
    dataUsed: ["gene coverage matrix", "assay catalog modalities"],
  },
  {
    path: "/public/gene/:geneId/info",
    page: "GeneInfoPage",
    area: "public",
    api: ["GET /common/gene/:geneId/info"],
    dataUsed: ["gene metadata", "external references", "annotation context"],
  },
  {
    path: "/public/contact",
    page: "ContactPage",
    area: "public",
    api: [],
    dataUsed: ["deployment contact copy"],
  },
  {
    path: "/public/genelists/:genelistId/view",
    page: "PublicGenelistPage",
    area: "public",
    api: ["GET /public/genelists/:genelistId/view_context"],
    dataUsed: ["gene list metadata", "gene rows", "assay filter context"],
  },
  {
    path: "/public/asp/:aspId/genes",
    page: "PublicAspGenesPage",
    area: "public",
    api: ["GET /public/asp/:aspId/genes"],
    dataUsed: ["ASP metadata", "genes"],
  },
  {
    path: "/coverage/blacklisted/:group",
    page: "CoverageBlacklistPage",
    area: "clinical",
    api: ["GET /coverage/blacklisted/:group", "DELETE /coverage/blacklist/entries/:id"],
    dataUsed: ["coverage blacklist entries"],
  },
  {
    path: "/admin",
    page: "AdminHub",
    area: "admin",
    api: [],
    dataUsed: ["static admin navigation"],
  },
  {
    path: "/admin/:resource",
    page: "AdminResourcePage",
    area: "admin",
    api: ["GET /users", "GET /roles", "GET /permissions", "GET /resources/asp", "GET /resources/aspc", "GET /resources/genelists", "GET /resources/samples"],
    dataUsed: ["managed resource list rows", "admin table actions"],
  },
  {
    path: "/admin/:resource/create",
    page: "AdminResourceEditorPage",
    area: "admin",
    api: ["GET /:resource/create_context", "POST /:resource"],
    dataUsed: ["form schema", "initial values", "validation endpoints"],
  },
  {
    path: "/admin/:resource/:id/edit",
    page: "AdminResourceEditorPage",
    area: "admin",
    api: ["GET /:resource/:id/context", "PUT /:resource/:id"],
    dataUsed: ["form schema", "record values", "validation endpoints"],
  },
  {
    path: "/admin/audit",
    page: "AdminAuditPage",
    area: "admin",
    api: ["GET /admin/audit"],
    dataUsed: ["audit event rows"],
  },
  {
    path: "/admin/schemas",
    page: "AdminSchemasPage",
    area: "admin",
    api: ["GET /admin/schemas"],
    dataUsed: ["collection schema specs"],
  },
  {
    path: "/notifications",
    page: "NotificationHistoryPage",
    area: "account",
    api: [],
    dataUsed: ["local notification history"],
  },
  {
    path: "/profile",
    page: "Profile",
    area: "account",
    api: ["GET /auth/session", "POST /auth/password/change"],
    dataUsed: ["session payload", "password change status"],
  },
]
