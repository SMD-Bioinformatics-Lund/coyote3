import { describe, expect, it } from "vitest"
import {
  routeEmptyState,
  routeErrorState,
  routeExpectedFields,
  uiRouteRegistry,
  type UiRouteAudit,
} from "./ui-route-registry"

describe("UI route registry", () => {
  it.each([
    ["asp", "AssaysPage", "AssayEditorPage"],
    ["aspc", "AssayConfigurationsPage", "AssayConfigurationEditorPage"],
    ["genelists", "GeneListsPage", "GeneListEditorPage"],
    ["users", "UsersPage", "UserEditorPage"],
    ["roles", "RolesPage", "RoleEditorPage"],
    ["permissions", "PermissionsPage", "PermissionEditorPage"],
    ["samples", "AdminSamplesPage", "AdminSampleEditorPage"],
  ])("assigns explicit routes to %s", (resource, page, editor) => {
    for (const suffix of ["", "/:id/view", "/:id/edit", "/create"]) {
      expect(uiRouteRegistry.find((entry) => entry.path === `/admin/${resource}${suffix}`))
        .toMatchObject({ page: resource === "asp" && suffix === "/create" ? "AssaySetupPage" : suffix ? editor : page })
    }
    expect(uiRouteRegistry.some((entry) => entry.path.includes(":resource"))).toBe(false)
  })

  it("contains unique route entries with an explicit page and area", () => {
    const paths = uiRouteRegistry.map((route) => route.path)
    expect(new Set(paths).size).toBe(paths.length)
    expect(uiRouteRegistry.every((route) => route.page && route.area)).toBe(true)
  })

  it("documents all major application areas and the fallback route", () => {
    expect(new Set(uiRouteRegistry.map((route) => route.area))).toEqual(
      new Set(["clinical", "public", "admin", "account", "system"]),
    )
    expect(uiRouteRegistry.at(-1)).toMatchObject({ path: "*", page: "NotFoundPage" })
  })

  it("prefers explicit expected fields and state messages", () => {
    const route: UiRouteAudit = {
      path: "/example",
      page: "Example",
      area: "system",
      api: [],
      dataUsed: ["fallback field"],
      expectedFields: ["explicit field"],
      emptyState: "Nothing configured.",
      errorState: "Request failed safely.",
    }
    expect(routeExpectedFields(route)).toEqual(["explicit field"])
    expect(routeEmptyState(route)).toBe("Nothing configured.")
    expect(routeErrorState(route)).toBe("Request failed safely.")
  })

  it("supplies consistent defaults for incomplete audit records", () => {
    const route: UiRouteAudit = {
      path: "/example",
      page: "Example",
      area: "system",
      api: [],
      dataUsed: ["value"],
    }
    expect(routeExpectedFields(route)).toEqual(["value"])
    expect(routeEmptyState(route)).toMatch(/empty table or no-data/)
    expect(routeErrorState(route)).toMatch(/page-local error state/)
  })
})
