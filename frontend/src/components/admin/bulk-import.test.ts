import { describe, expect, it } from "vitest"
import { bulkDefinitions, parseBulkFile } from "./bulk-import"

const config = bulkDefinitions.diagnoses
const parse = (text: string, name = "diagnoses.json") => parseBulkFile(text, name, Object.keys(config.example), [...config.required], config.identity)
describe("bulk resource files", () => {
  it("accepts the displayed JSON example and equivalent YAML", () => {
    expect(parse(JSON.stringify([config.example]))).toEqual([config.example])
    expect(parse("- diagnosis_id: example\n  display_name: Example\n  asp_ids: []", "diagnoses.yaml")).toEqual([{ diagnosis_id: "example", display_name: "Example", asp_ids: [] }])
  })
  it.each([
    ['{}', "list"], ['[]', "list"], ['[null]', "object"],
    ['[{"diagnosis_id":"a"}]', "display_name"],
    ['[{"diagnosis_id":"a","display_name":"A","created_by":"system"}]', "unsupported"],
    [JSON.stringify([config.example, config.example]), "duplicate"],
    [JSON.stringify(Array(101).fill(config.example)), "1–100"],
  ])("rejects invalid or ambiguous content", (value, message) => {
    expect(() => parse(value)).toThrow(message)
  })
  it("rejects duplicate YAML keys, aliases, custom tags and multiple documents", () => {
    for (const text of ["- diagnosis_id: a\n  diagnosis_id: b", "- &a {diagnosis_id: a, display_name: A}\n- *a", "- !custom value", "---\n[]\n---\n[]"]) {
      expect(() => parse(text, "input.yml")).toThrow()
    }
  })
  it("rejects wrong extensions and oversized content", () => {
    expect(() => parse("[]", "input.txt")).toThrow("JSON or YAML")
    expect(() => parse(" ".repeat(1024 * 1024 + 1))).toThrow("1 MiB")
  })
  it("uses the full assay configuration identity", () => {
    const records = [{ asp_id: "assay", diagnosis_id: "base", environment: "development" }, { asp_id: "assay", diagnosis_id: "base", environment: "production" }]
    expect(parseBulkFile(JSON.stringify(records), "config.json", Object.keys(records[0]), [], bulkDefinitions.aspc.identity)).toEqual(records)
  })
})
