// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { expect, it } from "vitest"
import { configurationContent, configurationWithMetadata } from "./configuration-transfer"

it("strips assay metadata while preserving embedded policy values and pinned references", () => {
  const source = { asp_id: "panel", version: 2, reporting: { rule_binding: { version: 5 } } }
  const content = configurationContent(source)
  expect(content).toEqual({ asp_id: "panel", reporting: source.reporting })
  expect(configurationWithMetadata(content, source)).toEqual(source)
})

it("adds only known metadata and never exports credentials or unknown response fields", () => {
  const content = { username: "synthetic", roles: ["reviewer"] }
  expect(configurationWithMetadata(content, { ...content, created_by: "author", version: 3,
    password: "not-a-real-secret", password_hash: "not-a-real-hash", unknown: "internal" })).toEqual({
    ...content, created_by: "author", version: 3,
  })
})

it("restores each assay's metadata in the original export order", () => {
  const source = [
    { asp_id: "panel-b", version: 3 },
    { asp_id: "panel-a", version: 2 },
  ]
  const portable = configurationContent(source)
  expect(portable).toEqual([{ asp_id: "panel-b" }, { asp_id: "panel-a" }])
  expect(configurationWithMetadata(portable, source)).toEqual(source)
})
