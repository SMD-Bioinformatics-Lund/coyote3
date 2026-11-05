import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`protects setup JSON import review in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    const original = { _id: "setup-1", asp_id: "synthetic", revision: 1, status: "published",
      created_by: "synthetic-author", content_editors: ["synthetic-author"], content: {
        panel: { asp_id: "synthetic", display_name: "Synthetic assay" }, scopes: ["base"],
        environments: ["production"], gene_lists: [], configurations: [],
      } }
    let imported: typeof original | null = null
    const panel_form = { fields: { display_name: { data_type: "str", label: "Display name" } } }
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/admin/assay-setups") {
        if (route.request().method() === "POST") {
          imported = { ...original, _id: "setup-2", asp_id: "imported-assay", status: "draft", content: route.request().postDataJSON() }
          return { status: 201, json: imported }
        }
        return { json: { items: imported ? [original, imported] : [original] } }
      }
      if (path.endsWith("/setup-1/context") || path.endsWith("/setup-2/context")) return { json: {
        setup: path.endsWith("/setup-2/context") ? imported : original, panel_form,
        diagnoses: [], environments: ["production"], history: [], rules: [],
      } }
    })
    await page.goto("/admin/assay-setups?setup=setup-1")
    await expect(page.getByLabel("Display name", { exact: true })).toBeVisible()
    const document = { ...original.content, panel: { asp_id: "imported-assay", display_name: "Imported assay" } }
    await page.getByLabel("Import assay setup JSON", { exact: true }).setInputFiles({ name: "setup.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(document)) })
    const editor = page.getByRole("textbox", { name: "Assay setup JSON", exact: true })
    await expect(editor).toBeVisible()
    await expect(page.getByLabel("Display name", { exact: true })).toHaveCount(0)
    await page.getByRole("button", { name: "Clear selection", exact: true }).click()
    await page.getByRole("alertdialog").getByRole("button", { name: "Keep editing" }).click()
    await expect(editor).toBeVisible()
    expect(imported).toBeNull()
    await page.screenshot({ path: testInfo.outputPath(`setup-import-review-${theme}-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole("button", { name: "Save assay setup", exact: true }).click()
    await expect(page).toHaveURL(/setup=setup-2$/)
    await expect(editor).toHaveCount(0)
    await expect(page.getByRole("alertdialog")).toHaveCount(0)
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Imported assay")
  })

  test(`imports Base ASPC into an existing draft in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    const writes: Record<string, unknown>[] = []
    let setup = { _id: "setup-1", asp_id: "synthetic", revision: 1, status: "draft",
      created_by: "synthetic-author", content_editors: ["synthetic-author"],
      content: { panel: { asp_id: "synthetic", asp_group: "solid", asp_category: "dna", display_name: "Synthetic assay" }, scopes: ["base"], environments: ["production"], gene_lists: [], configurations: [] as Record<string, unknown>[] } }
    const fields = {
      asp_id: { data_type: "str", hidden_mode: ["create"] },
      asp_group: { data_type: "str", hidden_mode: ["create"] },
      asp_category: { data_type: "str", hidden_mode: ["create"] },
      diagnosis_id: { data_type: "str", hidden_mode: ["create"] },
      environment: { data_type: "str", hidden_mode: ["create"] },
      display_name: { data_type: "str", label: "Configuration name" },
      filters: { data_type: "json", hidden_mode: ["create"] },
      reporting: { data_type: "json", hidden_mode: ["create"] },
    }
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/admin/assay-setups") return { json: { items: [setup] } }
      if (path === "/api/v1/admin/assay-setups/setup-1/context") return { json: { setup, panel_form: { fields: {} }, configuration_form: { fields }, diagnoses: [], environments: ["production"], readiness: { ready: true, issues: [] }, history: [] } }
      if (path === "/api/v1/admin/assay-setups/setup-1" && route.request().method() === "PUT") {
        const body = route.request().postDataJSON()
        expect(body.revision).toBe(1)
        writes.push(body)
        setup = { ...setup, revision: 2, content: body.content }
        return { json: setup }
      }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/assay-setups?setup=setup-1")
    await page.getByRole("button", { name: "5. Configurations", exact: true }).click()
    await page.getByRole("button", { name: "Add configuration base production" }).click()
    const document = { asp_id: "synthetic", asp_group: "solid", asp_category: "dna", diagnosis_id: "base", environment: "production", display_name: "Synthetic - Base Configuration", filters: { somatic: {} }, reporting: { report_sections: ["SNV"] } }
    const input = page.getByLabel("Import staged configuration JSON")
    await input.setInputFiles({ name: "wrong-assay.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ ...document, asp_id: "different-assay" })) })
    await expect(page.getByRole("alert")).toContainText("imported asp_id must match")
    expect(writes).toEqual([])
    await input.setInputFiles({ name: "aspc-base-production.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(document)) })
    await expect(page.getByLabel("Configuration name", { exact: true })).toHaveValue(document.display_name)
    expect(writes).toEqual([])
    await expect(page.getByRole("button", { name: "Import configuration JSON", exact: true })).toBeDisabled()
    await page.getByRole("button", { name: "6. Review", exact: true }).click()
    await page.getByRole("alertdialog").getByRole("button", { name: "Keep editing" }).click()
    await expect(page.getByLabel("Configuration name", { exact: true })).toHaveValue(document.display_name)
    await page.screenshot({ path: testInfo.outputPath(`configuration-import-${theme}-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save", exact: true }).first().click()
    await expect.poll(() => writes.length).toBe(1)
    expect((writes[0].content as { configurations: unknown[] }).configurations).toEqual([document])
    await expect(page.getByRole("cell", { name: "Configured", exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}

for (const width of [1440, 1024, 390]) {
  test(`assay setup starts with Base and resumes saved scope selections at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    let saved: Record<string, unknown> | null = null
    const panelForm = { fields: {
      asp_id: { label: "Assay identifier", data_type: "str", display_type: "text" },
      display_name: { label: "Display name", data_type: "str", display_type: "text" },
      asp_group: { data_type: "str", default: "hematology" },
      asp_family: { data_type: "str", default: "panel-dna" },
      asp_category: { data_type: "str", default: "dna" },
      expected_files: { label: "Expected files", data_type: "list", display_type: "checkbox-group",
        options: ["vcf_files", "cnv", "cnvprofile", "cov", "transloc", "biomarkers", "pgx"] },
    } }
    const context = () => ({ panel_form: panelForm, diagnoses: [{ diagnosis_id: "myeloid", display_name: "Myeloid", is_active: true }], environments: ["development", "production"], ...(saved ? { setup: saved, history: [], rules: [], readiness: { ready: false, issues: ["Missing required ASPC: base/production"] } } : {}) })
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/resources/genelists") return { json: {
        genelists: [{ isgl_id: "shared", name: "Shared list", asp_ids: [], asp_groups: [], is_active: true, version: 1 }],
        pagination: { has_next: false },
      } }
      if (path === "/api/v1/admin/assay-setups") {
        if (route.request().method() === "POST") {
          saved = { _id: "setup-1", asp_id: "synthetic-assay", content: route.request().postDataJSON(), status: "draft", revision: 1, created_by: "coyote3.admin", content_editors: ["coyote3.admin"] }
          expect((saved.content as { scopes: string[] }).scopes).toEqual(["base"])
          return { status: 201, json: saved }
        }
        return { json: { items: saved ? [saved] : [] } }
      }
      if (path.endsWith("/assay-setups/context") || path.endsWith("/assay-setups/setup-1/context")) return { json: context() }
      if (path === "/api/v1/admin/assay-setups/setup-1" && route.request().method() === "PUT") {
        saved = { ...saved, content: route.request().postDataJSON().content, revision: Number(saved?.revision) + 1 }
        return { json: saved }
      }
    })
    await page.goto("/admin/assay-setups?setup=new")
    await page.getByLabel("Assay identifier", { exact: true }).fill("synthetic-assay")
    await page.getByLabel("Display name", { exact: true }).fill("Synthetic assay")
    const fileOptions = page.locator(".form-option-group").first()
    await fileOptions.locator("label.form-option").filter({ hasText: "vcf_files" }).getByRole("checkbox").check()
    expect(await fileOptions.evaluate(element => getComputedStyle(element).boxShadow)).toContain("inset")
    await page.screenshot({ path: testInfo.outputPath(`setup-form-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save and continue", exact: true }).click()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeDisabled()
    await expect(page.getByRole("checkbox", { name: "production Required", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "production Required", exact: true })).toBeDisabled()
    await expect(page.getByRole("checkbox", { name: "Myeloid", exact: true })).not.toBeChecked()
    await page.getByRole("checkbox", { name: "Myeloid", exact: true }).check()
    await page.getByRole("checkbox", { name: "development", exact: true }).check()
    await page.getByRole("button", { name: "Save and continue" }).click()
    await expect(page.getByRole("region", { name: "Gene list workspace" })).toBeVisible()
    await expect(page.getByText("r2 · Draft", { exact: true })).toBeVisible()
    await page.getByRole("button", { name: "Link", exact: true }).click()
    await expect(page.getByText("Selected: shared", { exact: true })).toBeVisible()
    expect((saved!.content as { existing_gene_list_ids: string[] }).existing_gene_list_ids).toEqual(["shared"])
    await page.reload()
    await expect(page.getByRole("button", { name: /Synthetic assay · synthetic-assay · draft · Revision/ })).toBeVisible()
    await page.keyboard.press("Escape")
    await page.getByRole("button", { name: "2. Diagnoses", exact: true }).click()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "Myeloid", exact: true })).toBeChecked()
    await page.screenshot({ path: testInfo.outputPath(`setup-scopes-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    for (const [number, name] of [[3, "Gene lists"], [4, "Reporting rules"], [5, "Configurations"]] as const) {
      await page.getByRole("button", { name: `${number}. ${name}`, exact: true }).click()
      const next = page.getByRole("button", { name: "Next", exact: true })
      await expect(next).toBeVisible()
      const bounds = await next.boundingBox()
      expect(bounds).not.toBeNull()
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await page.screenshot({ path: testInfo.outputPath(`setup-step-${number}-${width}.png`), fullPage: true })
    }
    await page.getByRole("button", { name: "6. Review", exact: true }).click()
    await expect(page.getByRole("button", { name: "Submit for review" })).toBeDisabled()
    await expect(page.getByText("Missing required ASPC: base/production", { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`setup-review-${width}.png`), fullPage: true })
  })
}

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`copies staged ASPC settings into a new scope in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    const writes: unknown[] = []
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/resources/aspc") {
        if (route.request().method() === "POST") {
          writes.push(route.request().postDataJSON())
          return { json: { aspc_id: "synthetic_base_testing" } }
        }
        return { json: { assay_configs: [] } }
      }
      if (path === "/api/v1/admin/assay-setups") return { json: { items: [{ _id: "setup-1", asp_id: "synthetic", status: "draft" }] } }
      if (path === "/api/v1/admin/assay-setups/setup-1/context") return { json: { setup: { status: "draft", revision: 1, content: {
        panel: { asp_id: "synthetic", asp_category: "rna" },
        configurations: [{ aspc_id: "old", display_name: "Synthetic fusion", diagnosis_id: "base", environment: "production", verification_samples: { SYNTHETIC_A: [101, 202] } }],
      } } } }
      if (path === "/api/v1/resources/aspc/create_context") return { json: { form: { fields: {
        asp_id: { label: "Assay", display_type: "input" },
        diagnosis_id: { label: "Diagnosis", display_type: "input" },
        environment: { label: "Environment", display_type: "input" },
        display_name: { label: "Display name", display_type: "input" },
        verification_samples: { label: "Verification Samples", data_type: "json", display_type: "jsoneditor", default: {} },
      } } } }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/aspc")
    await page.getByRole("button", { name: "Copy from setup draft" }).click()
    await page.getByRole("combobox", { name: "Source setup draft" }).click()
    await page.getByRole("option", { name: "synthetic", exact: true }).click()
    await page.getByRole("combobox", { name: "Source staged configuration" }).click()
    await page.getByRole("option", { name: "Synthetic fusion · base / production" }).click()
    await page.screenshot({ path: testInfo.outputPath(`copy-source-${theme}-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole("link", { name: "Copy staged configuration as new" }).focus()
    await page.keyboard.press("Enter")
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Synthetic fusion")
    await expect(page.getByPlaceholder("Value", { exact: true })).toHaveValue("[101,202]")
    expect(writes).toEqual([])
    await page.getByLabel("Environment", { exact: true }).fill("testing")
    await page.getByRole("button", { name: "Save", exact: true }).first().click()
    await expect.poll(() => writes).toEqual([{ config: { asp_id: "synthetic", diagnosis_id: "base", environment: "testing", display_name: "Synthetic fusion", verification_samples: { SYNTHETIC_A: [101, 202] } } }])
  })
}

for (const [theme, width, initialStatus] of [["light", 1440, "draft"], ["dark", 390, "draft"], ["light", 1024, "submitted"]] as const) {
  test(`author activates ${initialStatus} without mandatory review in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    const actions: string[] = []
    let setup = {
      _id: "setup-1", asp_id: "synthetic", status: initialStatus as string, revision: 1,
      created_by: "synthetic-author", content_editors: ["synthetic-author"],
      content: { panel: { asp_id: "synthetic", display_name: "Synthetic assay" }, scopes: ["base"], environments: ["production"], gene_lists: [], configurations: [{ diagnosis_id: "base", environment: "production", display_name: "Synthetic production" }] },
    }
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/admin/assay-setups") return { json: { items: [setup] } }
      if (path === "/api/v1/admin/assay-setups/setup-1/context") return { json: {
        setup, panel_form: { fields: { display_name: { label: "Display name", display_type: "input" } } },
        diagnoses: [], environments: ["production"], history: [], readiness: { ready: true, issues: [] },
      } }
      if (path.startsWith("/api/v1/admin/assay-setups/setup-1/") && route.request().method() === "POST") {
        actions.push(path.split("/").at(-1)!)
        expect(route.request().postDataJSON()).toEqual({ revision: 1, reason: "" })
        setup = { ...setup, status: "published", revision: 2 }
        return { json: setup }
      }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/assay-setups?setup=setup-1")
    if (initialStatus === "draft") {
      const field = page.getByLabel("Display name", { exact: true })
      await expect(field).toBeEditable()
      await field.fill("Unsaved synthetic name")
      await page.getByRole("button", { name: "6. Review", exact: true }).click()
      const discard = page.getByRole("alertdialog", { name: "Discard unsaved changes?" })
      await expect(discard).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`unsaved-dialog-${theme}-${width}.png`), fullPage: true })
      await discard.getByRole("button", { name: "Keep editing" }).click()
      await expect(field).toHaveValue("Unsaved synthetic name")
      await page.getByRole("button", { name: "6. Review", exact: true }).click()
      await discard.getByRole("button", { name: "Discard changes" }).click()
    } else {
      await page.getByRole("button", { name: "6. Review", exact: true }).click()
    }
    await expect(page.getByText("Ready for activation", { exact: true })).toBeVisible()
    const publish = page.getByRole("button", { name: "Publish and activate", exact: true })
    await expect(publish).toBeEnabled()
    if (initialStatus === "draft") await expect(page.getByRole("button", { name: "Submit for review", exact: true })).toBeDisabled()
    expect(actions).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: testInfo.outputPath(`optional-review-${initialStatus}-${theme}-${width}.png`), fullPage: true })
    await publish.focus()
    await page.keyboard.press("Enter")
    await expect(page.getByText("Assay setup published. Manage subsequent changes from the individual resource pages.", { exact: true })).toBeVisible()
    expect(actions).toEqual(["publish"])
    await expect(publish).toHaveCount(0)
  })
}

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`history protection and assigned review complete in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    let actor = "synthetic-author"
    const actions: string[] = []
    let setup = {
      _id: "setup-1", asp_id: "synthetic", revision: 1, status: "draft",
      created_by: "synthetic-author", content_editors: ["synthetic-author"],
      reviewer: null as string | null, reviewed_by: null as string | null,
      published_by: null as string | null,
      content: { panel: { asp_id: "synthetic", display_name: "Synthetic assay" }, scopes: ["base"], environments: ["production"], existing_gene_list_ids: [], gene_lists: [], configurations: [] },
    }
    const panelForm = { fields: { display_name: { label: "Display name", display_type: "input" } } }
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: actor, roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/admin/assay-setups") return { json: { items: [setup] } }
      if (path === "/api/v1/admin/assay-setups/context") return { json: { panel_form: panelForm, diagnoses: [], environments: ["production"] } }
      if (path === "/api/v1/admin/assay-setups/setup-1/context") return { json: { setup, panel_form: panelForm, diagnoses: [], environments: ["production"], reviewers: [{ username: "colleague", name: "Synthetic reviewer" }], readiness: { ready: true, issues: [] }, history: [] } }
      if (path === "/api/v1/admin/assay-setups/setup-1/submit") {
        expect(route.request().postDataJSON()).toEqual({ revision: 1, reason: "", assignee: "colleague" })
        actions.push("submit")
        setup = { ...setup, revision: 2, status: "submitted", reviewer: "colleague" }
        return { json: setup }
      }
      if (path === "/api/v1/admin/assay-setups/setup-1/publish") {
        expect(route.request().postDataJSON()).toEqual({ revision: 2, reason: "" })
        actions.push("publish")
        setup = { ...setup, revision: 3, status: "published", reviewed_by: actor, published_by: actor }
        return { json: setup }
      }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/assay-setups?setup=setup-1")
    await expect(page.getByLabel("Display name", { exact: true })).toBeEditable()
    const navigation = page.getByRole("complementary", { name: "Assay setup navigation" })
    const editor = page.getByRole("region", { name: "Assay setup editor" })
    await navigation.getByRole("combobox", { name: "Filter assay setups by workflow state" }).selectOption("published")
    await expect(navigation.getByText("No setups match these filters.")).toBeVisible()
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Synthetic assay")
    await navigation.getByRole("combobox", { name: "Filter assay setups by workflow state" }).selectOption("draft")
    await navigation.getByRole("searchbox", { name: "Search assay setups" }).fill("SYNTHETIC")
    const row = navigation.getByRole("button", { name: /Synthetic assay · synthetic · draft/ })
    const draftColor = await row.getByText("Draft", { exact: true }).evaluate(element => getComputedStyle(element).backgroundColor)
    const workspace = page.getByRole("region", { name: "Assay setup workspace", exact: true })
    await expect(workspace.getByRole("button", { name: "Import JSON", exact: true })).toBeVisible()
    await expect(workspace.getByRole("complementary", { name: "Assay setup navigation" })).toBeVisible()
    await row.focus()
    await page.keyboard.press("Enter")
    await expect(row).toHaveAttribute("aria-pressed", "true")
    const left = await navigation.boundingBox()
    const right = await editor.boundingBox()
    expect(left).not.toBeNull()
    expect(right).not.toBeNull()
    if (width >= 1280) expect(right!.x).toBeGreaterThanOrEqual(left!.x + left!.width)
    else expect(right!.y).toBeGreaterThanOrEqual(left!.y + left!.height)
    await page.screenshot({ path: testInfo.outputPath(`setup-sidebar-${theme}-${width}.png`), fullPage: true })
    await navigation.getByRole("button", { name: "Collapse assay setup list" }).click()
    await navigation.getByRole("button", { name: "Expand assay setup list" }).click()
    await page.getByRole("button", { name: "New assay setup", exact: true }).click()
    await expect(page).toHaveURL(/setup=new$/)
    await page.getByLabel("Display name", { exact: true }).fill("Unsaved new assay")
    const dialog = page.getByRole("alertdialog", { name: "Discard unsaved changes?" })
    await page.goBack()
    await expect(dialog).toBeVisible()
    await dialog.getByRole("button", { name: "Keep editing" }).click()
    await expect(page).toHaveURL(/setup=new$/)
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Unsaved new assay")
    await page.goBack()
    await dialog.getByRole("button", { name: "Discard changes" }).click()
    await expect(page).toHaveURL(/setup=setup-1$/)
    await expect(page.getByLabel("Display name", { exact: true })).toBeEditable()
    await page.getByLabel("Display name", { exact: true }).fill("Unsaved saved assay")
    await page.goForward()
    await expect(dialog).toBeVisible()
    await dialog.getByRole("button", { name: "Keep editing" }).click()
    await expect(page).toHaveURL(/setup=setup-1$/)
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Unsaved saved assay")
    await page.goForward()
    await dialog.getByRole("button", { name: "Discard changes" }).click()
    await expect(page).toHaveURL(/setup=new$/)
    await page.goBack()
    await expect(page).toHaveURL(/setup=setup-1$/)
    expect(actions).toEqual([])
    await page.getByRole("button", { name: "6. Review", exact: true }).click()
    await expect(page.getByRole("button", { name: "Submit for review", exact: true })).toBeDisabled()
    await page.getByRole("combobox", { name: "Reviewer for optional review" }).click()
    await page.getByRole("option", { name: "Synthetic reviewer (colleague)" }).click()
    await page.getByRole("button", { name: "Submit for review", exact: true }).click()
    await expect(page.getByText("Assigned reviewer:", { exact: false })).toContainText("colleague")
    const reviewColor = await editor.getByText("r2 · Submitted", { exact: true }).evaluate(element => getComputedStyle(element).backgroundColor)
    expect(reviewColor).not.toBe(draftColor)
    await page.screenshot({ path: testInfo.outputPath(`assigned-review-${theme}-${width}.png`), fullPage: true })
    actor = "colleague"
    await page.reload()
    await page.getByRole("button", { name: "6. Review", exact: true }).click()
    await page.getByRole("button", { name: "Approve and activate", exact: true }).click()
    await expect(page.getByText("Reviewed by colleague", { exact: false })).toBeVisible()
    const publishedColor = await editor.getByText("r3 · Published", { exact: true }).evaluate(element => getComputedStyle(element).backgroundColor)
    expect(new Set([draftColor, reviewColor, publishedColor]).size).toBe(3)
    expect(actions).toEqual(["submit", "publish"])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}
