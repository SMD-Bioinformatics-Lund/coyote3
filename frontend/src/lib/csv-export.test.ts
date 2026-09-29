import { describe, expect, it } from "vitest"
import { escapeCsvCell } from "./csv-export"
import { rowsToCsv } from "./chart-export"

describe("spreadsheet-safe CSV", () => {
  it.each(["=1+1", "+SUM(1)", "-1+2", "@SUM(1)", "  =1", "\tformula", "\rformula"])("protects %j", (value) => {
    expect(escapeCsvCell(value, true)).toBe(`"'${value}"`)
  })
  it.each([0, -0.3, "-0.3", "1e-4", "TP53", ""])("preserves %j", (value) => {
    expect(escapeCsvCell(value)).toBe(String(value))
  })
  it("escapes headers and embedded delimiters in both export styles", () => {
    expect(escapeCsvCell('a"b,c', true)).toBe('"a""b,c"')
    expect(rowsToCsv([{ "=header": "=1+1", ratio: -0.3 }])).toBe("'=header,ratio\n'=1+1,-0.3")
  })
})
