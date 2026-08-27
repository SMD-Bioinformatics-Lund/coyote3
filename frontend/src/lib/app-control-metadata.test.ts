import { describe, expect, it } from "vitest"
import { APP_CONTROL_HELP, appControlHelp } from "./app-control-metadata"

const expectedControlKeys = [
  "enabled",
  "sample_ingest_enabled",
  "collection_writes_enabled",
  "maintenance_enabled",
  "dna_analysis_enabled",
  "rna_analysis_enabled",
  "reports_enabled",
  "variant_search_enabled",
  "knowledgebases_enabled",
  "ingest_workspace_enabled",
  "assay_catalog_enabled",
  "small_variant_enabled",
  "cnv_enabled",
  "fusion_enabled",
  "translocation_enabled",
  "audit_events_days",
  "notification_days",
  "disk_log_days",
  "gzip_disk_logs_after_days",
]

describe("application control metadata", () => {
  it("documents every persisted control exposed by the admin page", () => {
    expect(Object.keys(APP_CONTROL_HELP).sort()).toEqual(expectedControlKeys.sort())
    for (const definition of Object.values(APP_CONTROL_HELP)) {
      expect(definition.label).not.toBe("")
      expect(definition.summary).not.toBe("")
      expect(definition.enabledEffect).not.toBe("")
      expect(definition.disabledEffect).not.toBe("")
      expect(definition.operationalNote).not.toBe("")
    }
  })

  it("does not describe the master execution gate as a worker process switch", () => {
    const definition = appControlHelp("enabled")

    expect(definition.label).toBe("Allow background task execution")
    expect(definition.operationalNote).toContain("does not start or stop worker processes")
  })
})
