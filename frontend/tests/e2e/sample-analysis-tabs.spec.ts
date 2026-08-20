import { expect, test, type Page } from "@playwright/test"

type SampleContext = {
  sample: Record<string, unknown>
  analysis_sections: string[]
}

const dnaContext: SampleContext = {
  sample: {
    name: "DNA_001",
    asp_id: "hema_gmsv1",
    subpanel_id: "base",
    environment: "production",
    ingest_status: "ready",
    omics_layer: "dna",
    analysis_intents: ["somatic"],
    files: {
      vcf_files: "/data/DNA_001.vcf.gz",
      cnv: "/data/DNA_001.cnv.json",
      cov: "/data/DNA_001.coverage.json",
      transloc: "/data/DNA_001.translocations.vcf.gz",
    },
    data_counts: { snvs: 1, cnvs: 1, cov: true, transloc: 1 },
  },
  analysis_sections: ["SNV", "CNV", "TRANSLOCATION", "COVERAGE"],
}

const rnaContext: SampleContext = {
  sample: {
    name: "RNA_001",
    asp_id: "rna_fusion_v1",
    subpanel_id: "base",
    environment: "production",
    ingest_status: "ready",
    omics_layer: "rna",
    analysis_intents: ["somatic"],
    files: { fusion_files: "/data/RNA_001.fusions.json" },
    data_counts: { fusions: 1 },
  },
  analysis_sections: ["FUSION"],
}

const dnaSomaticAndGermlineContext: SampleContext = {
  sample: {
    ...dnaContext.sample,
    name: "DNA_BOTH_001",
    analysis_intents: ["somatic", "germline"],
  },
  analysis_sections: ["SNV"],
}

async function installApiFixtures(
  page: Page,
  context: SampleContext,
  analysisLayout: "classic" | "modern" = "modern",
) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname
    const emptyPage = { meta: { count: 0, page: 1, per_page: 50, has_next: false, has_previous: false } }

    if (path === "/api/v1/auth/whoami") {
      await route.fulfill({
        json: {
          username: "clinical.user",
          role: "user",
          ui_settings: { analysis_layout: analysisLayout },
        },
      })
      return
    }
    if (path === "/api/v1/public/assay-catalog/context") {
      await route.fulfill({ json: { nav_groups: [] } })
      return
    }
    if (path === "/api/v1/public/contact") {
      await route.fulfill({ json: { contacts: [], links: [] } })
      return
    }
    if (path.endsWith("/edit-context")) {
      await route.fulfill({ json: { ...context, comments: [] } })
      return
    }
    if (path.includes("/small-variants/comment-suggestion")) {
      await route.fulfill({ json: { suggested_text: "" } })
      return
    }
    if (path.endsWith("/small-variants")) {
      await route.fulfill({ json: { ...emptyPage, display_sections_data: { snvs: [] }, sample: context.sample } })
      return
    }
    if (path.endsWith("/cnvs")) {
      await route.fulfill({ json: { ...emptyPage, display_sections_data: { cnvs: [] }, sample: context.sample } })
      return
    }
    if (path.endsWith("/translocations")) {
      await route.fulfill({ json: { ...emptyPage, display_sections_data: { translocs: [] }, sample: context.sample } })
      return
    }
    if (path.endsWith("/coverage")) {
      await route.fulfill({ json: { cov_table: {}, sample: context.sample } })
      return
    }
    if (path.endsWith("/fusions")) {
      await route.fulfill({ json: { ...emptyPage, fusions: [], sample: context.sample } })
      return
    }
    await route.fulfill({ json: {} })
  })
}

function sampleAnalysisRequests(page: Page, sampleName: string) {
  const requests: string[] = []
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname
    if (path.includes(`/samples/${sampleName}/`)) requests.push(path)
  })
  return requests
}

test("DNA sample tabs and requests are limited to its ASPC analysis selection", async ({ page }) => {
  await installApiFixtures(page, dnaContext)
  const requests = sampleAnalysisRequests(page, "DNA_001")

  await page.goto("/samples/DNA_001")
  await expect(page.getByRole("tab", { name: "Somatic SNVs" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "CNVs" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Translocations" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Coverage" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Germline SNVs" })).toHaveCount(0)
  await expect(page.getByRole("tab", { name: "Fusions" })).toHaveCount(0)
  expect(requests.some((path) => path.endsWith("/fusions"))).toBe(false)
  expect(requests.some((path) => path.endsWith("/small-variants"))).toBe(false)

  await page.getByRole("tab", { name: "Somatic SNVs" }).click()
  await expect.poll(() => requests.some((path) => path.endsWith("/small-variants"))).toBe(true)
  expect(requests.some((path) => path.endsWith("/fusions"))).toBe(false)
})

test("RNA sample requests the fusion endpoint only after the configured fusion tab is opened", async ({ page }) => {
  await installApiFixtures(page, rnaContext)
  const requests = sampleAnalysisRequests(page, "RNA_001")

  await page.goto("/samples/RNA_001")
  await expect(page.getByRole("tab", { name: "Fusions" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Somatic SNVs" })).toHaveCount(0)
  await expect(page.getByRole("tab", { name: "CNVs" })).toHaveCount(0)
  await expect(page.getByRole("tab", { name: "Translocations" })).toHaveCount(0)
  await expect(page.getByRole("tab", { name: "Coverage" })).toHaveCount(0)
  expect(requests.some((path) => path.endsWith("/fusions"))).toBe(false)

  await page.getByRole("tab", { name: "Fusions" }).click()
  await expect.poll(() => requests.some((path) => path.endsWith("/fusions"))).toBe(true)
  expect(requests.some((path) => path.endsWith("/small-variants"))).toBe(false)
})

test("germline SNVs use an isolated intent-specific request", async ({ page }) => {
  await installApiFixtures(page, dnaSomaticAndGermlineContext)
  const requests = sampleAnalysisRequests(page, "DNA_BOTH_001")

  await page.goto("/samples/DNA_BOTH_001")
  await expect(page.getByRole("tab", { name: "Somatic SNVs" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Germline SNVs" })).toBeVisible()

  const germlineRequest = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return (
      url.pathname === "/api/v1/samples/DNA_BOTH_001/small-variants" &&
      url.searchParams.get("intent") === "germline"
    )
  })
  await page.getByRole("tab", { name: "Germline SNVs" }).click()
  await germlineRequest

  expect(requests.some((path) => path.endsWith("/cnvs"))).toBe(false)
  expect(requests.some((path) => path.endsWith("/fusions"))).toBe(false)
})

test("selected analysis tab survives a browser reload", async ({ page }) => {
  await installApiFixtures(page, dnaContext)

  await page.goto("/samples/DNA_001")
  await page.getByRole("tab", { name: "CNVs" }).click()
  await expect(page).toHaveURL(/samples\/DNA_001\?tab=cnvs/)
  await expect(page.getByRole("tab", { name: "CNVs" })).toHaveAttribute("aria-selected", "true")

  await page.reload()

  await expect(page.getByRole("tab", { name: "CNVs" })).toHaveAttribute("aria-selected", "true")
  await expect(page).toHaveURL(/samples\/DNA_001\?tab=cnvs/)
})

test("analysis request failures remain on the selected tab", async ({ page }) => {
  await installApiFixtures(page, dnaContext)
  await page.route("**/api/v1/samples/DNA_001/cnvs**", async (route) => {
    await route.fulfill({ status: 503, json: { detail: "CNV analysis is temporarily unavailable" } })
  })

  await page.goto("/samples/DNA_001?tab=cnvs")

  await expect(page.getByRole("tab", { name: "CNVs" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByText("Error loading CNVs")).toBeVisible()
  await expect(page).toHaveURL(/samples\/DNA_001\?tab=cnvs/)
})

test("combined layout presents enabled finding sections on one page", async ({ page }) => {
  await installApiFixtures(page, dnaContext, "classic")
  const requests = sampleAnalysisRequests(page, "DNA_001")

  await page.goto("/samples/DNA_001")
  await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Somatic SNVs" })).toHaveCount(0)

  await page.getByRole("tab", { name: "Findings" }).click()

  await expect(page.getByRole("heading", { name: "Somatic SNVs" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "CNVs" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Translocations" })).toBeVisible()
  const snvCard = page
    .getByRole("heading", { name: "Somatic SNVs" })
    .locator("xpath=ancestor::*[@data-testid='analysis-table-card']")
  await expect(snvCard.getByPlaceholder("Search variants, genes, HGVS, flags...")).toBeVisible()
  await expect.poll(() => requests.some((path) => path.endsWith("/small-variants"))).toBe(true)
  await expect.poll(() => requests.some((path) => path.endsWith("/cnvs"))).toBe(true)
  await expect.poll(() => requests.some((path) => path.endsWith("/translocations"))).toBe(true)

  const cnvSectionHeader = page.getByRole("heading", { name: "CNVs" }).locator("xpath=..")
  await cnvSectionHeader.getByRole("button", { name: "Filters" }).click()
  await expect(page.getByText("CNV Thresholds")).toBeVisible()
  await cnvSectionHeader.getByRole("button", { name: "Filters" }).click()
  await expect(page.getByText("CNV Thresholds")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Show Somatic SNVs filters" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Show CNVs filters" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Show Translocations filters" })).toBeVisible()

  await page.getByRole("button", { name: "Show Translocations filters" }).click()
  await expect(page.getByText("Fusion/Translocation Gene Lists")).toBeVisible()
})
