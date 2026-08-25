export type AppControlHelp = {
  label: string
  summary: string
  enabledEffect: string
  disabledEffect: string
  operationalNote: string
}

export const APP_CONTROL_HELP: Record<string, AppControlHelp> = {
  enabled: {
    label: "Allow background task execution",
    summary: "Master application gate for every controlled Celery task family.",
    enabledEffect: "A queued task may run when its own task-family gate is also enabled.",
    disabledEffect: "Controlled tasks return a disabled result before doing application work.",
    operationalNote: "This does not start or stop worker processes, resize the worker pool, cancel running work, or release worker processes.",
  },
  sample_ingest_enabled: {
    label: "Complete sample ingestion",
    summary: "One gate for watch-folder discovery, submitted sample bundles, and all dependent analysis writes.",
    enabledEffect: "New ingest transactions may validate a manifest and atomically load the sample with every declared analysis resource.",
    disabledEffect: "Watch scans and manually queued sample-ingest jobs exit before changing clinical sample collections.",
    operationalNote: "The watch schedule is deployment configuration. Turning this off does not cancel an ingest transaction that is already running.",
  },
  collection_writes_enabled: {
    label: "Validated collection writes",
    summary: "Controls generic background insert and upsert tasks for schema-registered collections.",
    enabledEffect: "Validated single-document and batch write jobs may modify supported collections.",
    disabledEffect: "Generic collection-write jobs exit before persisting documents.",
    operationalNote: "This gate does not block ordinary synchronous API writes outside these Celery tasks.",
  },
  maintenance_enabled: {
    label: "Operational maintenance",
    summary: "Controls scheduled retention cleanup and explicitly requested reference knowledgebase refresh jobs.",
    enabledEffect: "Maintenance may delete expired audit events, manage disk logs, and refresh public OncoKB reference records from the HGNC catalogue.",
    disabledEffect: "Maintenance tasks exit without applying cleanup policies or external reference refreshes.",
    operationalNote: "The master background-task gate must also be enabled. MongoDB TTL expiry can still operate independently.",
  },
  dna_analysis_enabled: {
    label: "DNA analysis",
    summary: "Controls small variants, CNVs, translocations, biomarkers, and coverage workflows.",
    enabledEffect: "DNA tabs and routes are visible and their APIs accept requests.",
    disabledEffect: "DNA navigation is hidden and governed APIs return HTTP 503.",
    operationalNote: "Stored DNA data is retained and becomes available again when the module is enabled.",
  },
  rna_analysis_enabled: {
    label: "RNA analysis",
    summary: "Controls RNA fusion and expression workflows.",
    enabledEffect: "RNA tabs and routes are visible and their APIs accept requests.",
    disabledEffect: "RNA navigation is hidden and governed APIs return HTTP 503.",
    operationalNote: "Stored RNA data is retained and becomes available again when the module is enabled.",
  },
  reports_enabled: {
    label: "Reports",
    summary: "Controls clinical report preview, rendering, saving, and retrieval.",
    enabledEffect: "Reporting routes are visible and report APIs accept requests.",
    disabledEffect: "Report navigation is hidden and governed APIs return HTTP 503.",
    operationalNote: "Previously saved report data is retained.",
  },
  variant_search_enabled: {
    label: "Tiered variant search",
    summary: "Controls cross-sample search of tiered variants and annotation text.",
    enabledEffect: "Variant-search navigation and APIs are available.",
    disabledEffect: "Variant-search navigation is hidden and governed APIs return HTTP 503.",
    operationalNote: "Tiering within an individual sample remains part of DNA analysis.",
  },
  knowledgebases_enabled: {
    label: "Knowledgebases",
    summary: "Controls gene context and local or external knowledgebase lookups.",
    enabledEffect: "Knowledgebase actions and APIs are available.",
    disabledEffect: "Governed knowledgebase APIs return HTTP 503.",
    operationalNote: "Core stored variant annotations remain visible; optional evidence lookups are unavailable.",
  },
  ingest_workspace_enabled: {
    label: "Ingest workspace",
    summary: "Controls manual sample upload, validation, and queue-submission routes.",
    enabledEffect: "Authorized users can open the ingest workspace and call its APIs.",
    disabledEffect: "The workspace is hidden and governed APIs return HTTP 503.",
    operationalNote: "Watch-folder execution is governed separately by Complete sample ingestion.",
  },
  assay_catalog_enabled: {
    label: "Assay catalog",
    summary: "Controls public catalog, matrix, assay-gene, and gene-list reference views.",
    enabledEffect: "Catalog navigation and public APIs are available.",
    disabledEffect: "Catalog navigation is hidden and governed public APIs return HTTP 503.",
    operationalNote: "About and contact pages remain available.",
  },
  small_variant_enabled: {
    label: "Small-variant tiering",
    summary: "Controls Tier 1-4 classification actions for SNVs and small indels.",
    enabledEffect: "Authorized users can add and remove small-variant tiers.",
    disabledEffect: "Tier actions are hidden; existing classifications remain readable.",
    operationalNote: "The backend classification contract and stored annotation history are retained.",
  },
  cnv_enabled: {
    label: "CNV tiering",
    summary: "Controls Tier 1-4 classification actions for copy-number findings.",
    enabledEffect: "Authorized users can add and remove CNV tiers.",
    disabledEffect: "Tier actions are hidden; existing classifications remain readable.",
    operationalNote: "Disabled by default until the clinical CNV tiering workflow is released.",
  },
  fusion_enabled: {
    label: "Fusion tiering",
    summary: "Controls Tier 1-4 classification actions for RNA fusion findings.",
    enabledEffect: "Authorized users can add and remove fusion tiers.",
    disabledEffect: "Tier actions are hidden; existing classifications remain readable.",
    operationalNote: "Review flags and reporting inclusion remain separate controls.",
  },
  translocation_enabled: {
    label: "Translocation tiering",
    summary: "Controls Tier 1-4 classification actions for DNA translocations.",
    enabledEffect: "Authorized users can add and remove translocation tiers.",
    disabledEffect: "Tier actions are hidden; existing classifications remain readable.",
    operationalNote: "Disabled by default until the clinical translocation tiering workflow is released.",
  },
  audit_events_days: {
    label: "Audit event retention",
    summary: "Number of days audit events remain eligible for operational review.",
    enabledEffect: "New events receive the configured expiry horizon and maintenance removes older events.",
    disabledEffect: "Not applicable; enter a value from 30 to 3650 days.",
    operationalNote: "MongoDB TTL expiry and explicit retention maintenance form separate cleanup layers.",
  },
  notification_days: {
    label: "Notification retention",
    summary: "Number of days persisted user notifications should be retained.",
    enabledEffect: "The value becomes the active notification retention policy.",
    disabledEffect: "Not applicable; enter a value from 7 to 3650 days.",
    operationalNote: "Retention affects persisted notifications, not transient browser toasts.",
  },
  disk_log_days: {
    label: "Disk log retention",
    summary: "Maximum age of application log files retained on the configured log volume.",
    enabledEffect: "Maintenance deletes matching log files older than this number of days.",
    disabledEffect: "Not applicable; enter a value from 1 to 3650 days.",
    operationalNote: "Container stdout and logs held by an external logging platform are outside this policy.",
  },
  gzip_disk_logs_after_days: {
    label: "Gzip disk logs after",
    summary: "Age at which plain application log files are compressed on disk.",
    enabledEffect: "Maintenance compresses eligible plain log files after this number of days.",
    disabledEffect: "Not applicable; enter a value from 1 to the disk-log retention value.",
    operationalNote: "Already compressed files are left unchanged.",
  },
}

export function appControlHelp(key: string): AppControlHelp {
  return APP_CONTROL_HELP[key] || {
    label: key,
    summary: "Application control.",
    enabledEffect: "The control is enabled.",
    disabledEffect: "The control is disabled.",
    operationalNote: "No additional operational guidance is registered.",
  }
}
