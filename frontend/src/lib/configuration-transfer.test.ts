import { expect, it } from "vitest"
import { configurationContent, configurationWithMetadata } from "./configuration-transfer"

it("strips setup record metadata without changing embedded policy values or pinned references", () => {
  const source = { revision: 9, created_by: "author", panel: { asp_id: "panel", version: 8 },
    gene_lists: [{ isgl_id: "genes", genes: ["TP53"], created_on: "old", version: 3 }],
    configurations: [{ asp_id: "panel", content_hash: "old", reporting: { rule_binding: { version: 5 } } }],
    content: { condition: { field: "version", value: { version: 7, status: "valid" } } } }
  const before = structuredClone(source)
  expect(configurationContent(source)).toEqual({ panel: { asp_id: "panel" },
    gene_lists: [{ isgl_id: "genes", genes: ["TP53"] }],
    configurations: [{ asp_id: "panel", reporting: { rule_binding: { version: 5 } } }], content: source.content })
  expect(source).toEqual(before)
})

it("adds only known metadata and never exports credentials or unknown response fields", () => {
  const content = { username: "synthetic", roles: ["reviewer"] }
  expect(configurationWithMetadata(content, { ...content, created_by: "author", version: 3,
    password: "not-a-real-secret", password_hash: "not-a-real-hash", unknown: "internal" })).toEqual({
    ...content, created_by: "author", version: 3,
  })
})

it("round-trips metadata-inclusive ordered record lists and setup children", () => {
  const source = [{ panel: { asp_id: "panel", version: 3 }, status: "published", revision: 2,
    gene_lists: [{ isgl_id: "genes", version: 4 }], configurations: [] }]
  const portable = configurationContent(source)
  expect(configurationWithMetadata(portable, source)).toEqual(source)
  expect(configurationContent(configurationWithMetadata(portable, source))).toEqual(portable)
})
