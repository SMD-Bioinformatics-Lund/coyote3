import { describe, expect, it } from "vitest"
import {
  hasAnyPermission,
  hasPermission,
  isSuperuser,
  type CurrentUserAccess,
} from "./access-control"

function user(overrides: Partial<CurrentUserAccess> = {}): CurrentUserAccess {
  return {
    username: "manager.one",
    roles: ["manager"],
    role: "manager",
    access_level: 99,
    permissions: [],
    ...overrides,
  }
}

describe("admin capability checks", () => {
  it("allows an explicitly assigned permission without an admin role", () => {
    expect(hasPermission(user({ permissions: ["assay.config:edit"] }), "assay.config:edit"))
      .toBe(true)
  })

  it("denies an unassigned action even when another admin permission exists", () => {
    expect(hasPermission(user({ permissions: ["assay.config:view"] }), "assay.config:edit"))
      .toBe(false)
  })

  it("supports navigation checks across several capabilities", () => {
    expect(hasAnyPermission(user({ permissions: ["audit_log:view"] }), [
      "user:list",
      "audit_log:view",
    ])).toBe(true)
  })

  it("keeps the explicit superuser bypass", () => {
    const superuser = user({ roles: ["superuser"], role: "superuser" })
    expect(isSuperuser(superuser)).toBe(true)
    expect(hasPermission(superuser, "permission.not.in.catalog")).toBe(true)
  })
})
