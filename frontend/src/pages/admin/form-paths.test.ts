import { expect, it } from "vitest"
import { readFormPath, writeFormPath } from "./form-paths"

it("writes nested arrays without literal dotted keys or mutation", () => {
  const source = { somatic: { snv: { snvlists: ["old"], min_depth: 100 } } }
  const next = writeFormPath(source, "somatic.snv.snvlists", ["new"])
  expect(readFormPath(next, "somatic.snv.snvlists")).toEqual(["new"])
  expect(readFormPath(next, "somatic.snv.min_depth")).toBe(100)
  expect(next).not.toHaveProperty(["somatic.snv.snvlists"])
  expect(source.somatic.snv.snvlists).toEqual(["old"])
})
