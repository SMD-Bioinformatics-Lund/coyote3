import { describe, expect, it } from "vitest"
import { specs } from "./resource-specs"

const expectedPermissions = {
  users: ["user:list", "user:view", "user:create", "user:edit", "user:delete"],
  roles: ["role:list", "role:view", "role:create", "role:edit", "role:delete"],
  permissions: [
    "permission.policy:list",
    "permission.policy:view",
    "permission.policy:create",
    "permission.policy:edit",
    "permission.policy:delete",
  ],
  asp: [
    "assay.panel:list",
    "assay.panel:view",
    "assay.panel:create",
    "assay.panel:edit",
    "assay.panel:delete",
  ],
  aspc: [
    "assay.config:list",
    "assay.config:view",
    "assay.config:create",
    "assay.config:edit",
    "assay.config:delete",
  ],
  genelists: [
    "gene_list.insilico:list",
    "gene_list.insilico:view",
    "gene_list.insilico:create",
    "gene_list.insilico:edit",
    "gene_list.insilico:delete",
  ],
  samples: [
    "sample:list:global",
    "sample:view:global",
    "internal.ingest:manage",
    "sample:edit:global",
    "sample:delete:global",
  ],
} as const

describe("admin resource permission matrix", () => {
  it("keeps every resource action tied to its explicit capability", () => {
    for (const [resource, permissions] of Object.entries(expectedPermissions)) {
      expect(Object.values(specs[resource].permissions)).toEqual(permissions)
    }
  })

  it("does not reuse a permission across independent CRUD actions", () => {
    for (const spec of Object.values(specs)) {
      expect(new Set(Object.values(spec.permissions)).size).toBe(5)
    }
  })
})
