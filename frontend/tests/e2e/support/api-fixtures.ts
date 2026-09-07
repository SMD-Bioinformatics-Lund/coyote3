import type { Page, Route } from "@playwright/test"

type ApiResponse = {
  status?: number
  json?: unknown
}

export type ApiResolver = (
  path: string,
  url: URL,
  route: Route,
) => ApiResponse | undefined | Promise<ApiResponse | undefined>

const enabledModules = {
  dna_analysis: { enabled: true, label: "DNA analysis", description: "DNA analysis features." },
  rna_analysis: { enabled: true, label: "RNA analysis", description: "RNA analysis features." },
  reports: { enabled: true, label: "Clinical reporting", description: "Report workflows." },
  variant_search: { enabled: true, label: "Variant search", description: "Tiered variant search." },
  knowledgebases: { enabled: true, label: "Knowledgebases", description: "Knowledgebase views." },
  ingest_workspace: { enabled: true, label: "Ingest workspace", description: "Ingest operations." },
  assay_catalog: { enabled: true, label: "Assay catalog", description: "Catalog and matrix views." },
}

export async function installApiFixtures(page: Page, resolver?: ApiResolver) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/^.*\/api\/v1/, "/api/v1")
    const custom = await resolver?.(path, url, route)
    if (custom) {
      await route.fulfill({ status: custom.status ?? 200, json: custom.json ?? {} })
      return
    }

    if (path === "/api/v1/auth/whoami") {
      await route.fulfill({
        json: {
          username: "coyote3.admin",
          role: "admin",
          roles: ["superuser", "admin"],
          access_level: 99_999,
          permissions: [
            "app.controls:view",
            "app.controls:edit",
            "notification.broadcast:create",
          ],
        },
      })
      return
    }
    if (path === "/api/v1/public/modules") {
      await route.fulfill({ json: { modules: enabledModules } })
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
    if (path === "/api/v1/notifications") {
      await route.fulfill({ json: { notifications: [] } })
      return
    }
    await route.fulfill({ json: {} })
  })
}

export function modulePayload(overrides: Record<string, { enabled: boolean; label: string; description: string }>) {
  return { modules: { ...enabledModules, ...overrides } }
}
