import { expect, test } from "@playwright/test"
import { installApiFixtures, modulePayload } from "./support/api-fixtures"

test("dashboard presents distinct workload and panel capability information", async ({ page }) => {
  await installApiFixtures(page, (path) => {
    if (path !== "/api/v1/dashboard/summary") return
    return {
      json: {
        total_samples: 8,
        analysed_samples: 5,
        pending_samples: 3,
        variant_stats: { small_variants: 1200, unique_variants: 900, cnvs: 14 },
        user_samples_stats: { hema_gmsv1: { total: 4, analysed: 2, pending: 2 } },
        sample_stats: {
          profiles: { production: 6, validation: 2 },
          ingest_statuses: { ready: 7, processing: 1 },
          omics_layers: { dna: 6, rna: 2 },
          sequencing_scopes: { panel: 8 },
          pair_count: { paired: 5, unpaired: 3 },
        },
        tier_stats: { total: { tier1: 2, tier2: 3, tier3: 1, tier4: 0 } },
        quality_stats: { analysed_rate_percent: 62.5 },
        panel_gene_stats_grouped: {
          hematology: [{ asp_id: "hema_gmsv1", display_name: "Hematology GMSv1", covered_genes_count: 385, germline_genes_count: 20 }],
        },
        panel_portfolio: { active_panels: 1, assay_groups: 1, accredited_panels: 1, covered_gene_assignments: 385, germline_gene_assignments: 20 },
        panel_analysis_capabilities: [
          { analysis_type: "SNV", enabled: 2, reportable: 2 },
          { analysis_type: "CNV", enabled: 2, reportable: 1 },
        ],
        user_scope_summary: {
          total_samples: 8,
          pending_samples: 3,
          recent_samples: [],
          sample_stats: {
            profiles: { production: 6, validation: 2 },
            pipelines: [
              { name: "SomaticPanelPipeline", version: "3.2.0", count: 6, analysed: 4 },
              { name: "RnaFusionPipeline", version: "2.1.0", count: 2, analysed: 1 },
            ],
          },
        },
        capacity_counts: { users: 12, roles: 4 },
      },
    }
  })

  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  await expect(page.getByText("Review Workload")).toBeVisible()
  await expect(page.getByText("Panel Analysis Capability")).toBeVisible()
  await expect(page.getByText("Panel Portfolio")).toBeVisible()
  await expect(page.getByText("Panel Review Workload")).toHaveCount(0)
  await expect(page.getByText("Pipeline throughput")).toBeVisible()
  await expect(page.getByRole("img", { name: /SomaticPanelPipeline 3\.2\.0: 4 analysed, 2 awaiting review/ })).toBeVisible()

  const svgDownloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export Gene coverage per assay chart as SVG" }).click()
  const svgDownload = await svgDownloadPromise
  const stream = await svgDownload.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream) chunks.push(Buffer.from(chunk))
  const exportedSvg = Buffer.concat(chunks).toString("utf8")

  expect(exportedSvg).toContain("Hematology GMSv1")
  expect(exportedSvg).toContain('class="recharts-surface"')
  expect(exportedSvg).not.toContain('class="lucide lucide-download')

  const pngDownloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export Gene coverage per assay chart as PNG" }).click()
  const pngDownload = await pngDownloadPromise
  const pngStream = await pngDownload.createReadStream()
  const pngChunks: Buffer[] = []
  for await (const chunk of pngStream) pngChunks.push(Buffer.from(chunk))
  const exportedPng = Buffer.concat(pngChunks)

  expect(exportedPng.subarray(1, 4).toString("ascii")).toBe("PNG")
  expect(exportedPng.readUInt32BE(16)).toBeGreaterThan(500)
  expect(exportedPng.readUInt32BE(20)).toBeGreaterThan(150)
})

test("samples switch between live and reported records without a reload", async ({ page }) => {
  await installApiFixtures(page, (path) => {
    if (path === "/api/v1/auth/whoami") {
      return {
        json: {
          username: "coyote3.admin",
          role: "admin",
          roles: ["superuser", "admin"],
          access_level: 99_999,
          permissions: [],
          ui_settings: { sample_list_layout: "modern", sample_list_modern_view_tried: true },
        },
      }
    }
    if (path !== "/api/v1/samples") return
    return {
      json: {
        live_samples: [{ name: "DNA_LIVE_001", case_id: "CASE_LIVE_001", environment: "production", asp_id: "hema_gmsv1", subpanel_id: "hem", ingest_status: "ready", data_counts: { snvs: 12 } }],
        done_samples: [{ name: "DNA_REPORTED_001", case_id: "CASE_REPORTED_001", environment: "production", asp_id: "solid_gmsv3", subpanel_id: "colon", ingest_status: "ready", reported: true, data_counts: { snvs: 4 } }],
      },
    }
  })

  await page.goto("/samples")
  await expect(page.getByText("DNA_LIVE_001")).toBeVisible()
  await expect(page.getByText("DNA_REPORTED_001")).toHaveCount(0)
  await page.getByRole("tab", { name: /Reported samples/i }).click()
  await expect(page.getByText("DNA_REPORTED_001")).toBeVisible()
  await expect(page.getByText("DNA_LIVE_001")).toHaveCount(0)
  await expect(page).toHaveURL(/sample_tab=reported/)
})

test("disabled modules block direct routes with an operational explanation", async ({ page }) => {
  await installApiFixtures(page, (path) => {
    if (path !== "/api/v1/public/modules") return
    return {
      json: modulePayload({
        reports: {
          enabled: false,
          label: "Clinical reporting",
          description: "Reporting is temporarily disabled for maintenance.",
        },
      }),
    }
  })

  await page.goto("/reports")
  await expect(page.getByRole("heading", { name: "Clinical reporting is unavailable" })).toBeVisible()
  await expect(page.getByText("Reporting is temporarily disabled for maintenance.")).toBeVisible()
})

test("public matrix performs a server-side gene search and preserves gene links", async ({ page }) => {
  const requestedGenes: string[] = []
  await installApiFixtures(page, (path, url) => {
    if (path !== "/api/v1/public/assay-catalog-matrix/context") return
    const gene = url.searchParams.get("gene") || ""
    requestedGenes.push(gene)
    return {
      json: {
        columns: [{ mod: "dna", modality_label: "DNA", cat: "panel::hematology::hema_gmsv1::base", isgl_key: "hem", isgl_label: "Hematology" }],
        genes: gene ? [gene] : ["TP53", "DNMT3A"],
        matrix: { TP53: { dna: { "panel::hematology::hema_gmsv1::base": { hem: true } } } },
        page: 1,
        per_page: 100,
        total: gene ? 1 : 2,
        has_next: false,
        has_previous: false,
      },
    }
  })

  await page.goto("/public/matrix")
  await expect(page.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/public/gene/TP53/info")
  await page.getByLabel("Gene search").fill("TP53")
  await page.getByRole("button", { name: "Search" }).click()
  await expect.poll(() => requestedGenes.at(-1)).toBe("TP53")
  await expect(page.getByText('1 visible catalog column(s) for "TP53"', { exact: true })).toBeVisible()
})

test("profile edits persist through the dedicated profile endpoint", async ({ page }) => {
  let savedProfile: unknown
  await installApiFixtures(page, async (path, _url, route) => {
    if (path === "/api/v1/auth/session") {
      return {
        json: {
          user: {
            username: "clinical.user",
            firstname: "Clinical",
            lastname: "User",
            fullname: "Clinical User",
            job_title: "Scientist",
            role: "user",
            roles: ["user"],
            auth_type: ["local"],
            permissions: [],
          },
        },
      }
    }
    if (path === "/api/v1/auth/profile") {
      savedProfile = route.request().postDataJSON()
      return { json: { status: "ok" } }
    }
  })

  await page.goto("/profile")
  await page.getByLabel("Display name").fill("Clinical Reviewer")
  await page.getByRole("button", { name: "Save profile" }).click()
  await expect.poll(() => savedProfile).toMatchObject({ fullname: "Clinical Reviewer" })
})

test("notification broadcaster confirms and sends the selected audience", async ({ page }) => {
  let broadcast: unknown
  await installApiFixtures(page, async (path, _url, route) => {
    if (path === "/api/v1/admin/notifications/recipients") {
      return { json: { users: [], roles: [{ role_id: "manager", label: "Manager", user_count: 2 }] } }
    }
    if (path === "/api/v1/admin/notifications/broadcast") {
      broadcast = route.request().postDataJSON()
      return { json: { recipient_count: 2 } }
    }
  })

  await page.goto("/admin/notifications")
  await page.getByLabel("Title").fill("Scheduled maintenance")
  await page.getByLabel("Message").fill("The service will restart at 18:00.")
  await page.getByRole("button", { name: "By role" }).click()
  await page.getByRole("checkbox", { name: /Manager/ }).check()
  await page.getByRole("button", { name: "Send" }).click()
  await expect(page.getByText("This message will be sent to active users in 1 selected role(s).", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Send notification" }).click()
  await expect.poll(() => broadcast).toMatchObject({ audience: "roles", role_ids: ["manager"] })
})
