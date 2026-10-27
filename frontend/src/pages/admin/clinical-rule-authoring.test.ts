import { describe, expect, it } from "vitest"
import { sectionStarter } from "./clinical-rule-authoring"

const scope = { asp_id: "synthetic", diagnosis_id: "base", analyte: "dna" as const, language: "sv", name: "Synthetic" }

describe("Report section starters", () => {
  it("builds complementary SNV sentences with stable purpose-based IDs", () => {
    const block = sectionStarter([], "snv_summary", scope)
    expect(block.analysis).toBe("SNV")
    expect(block.evaluation.mode).toBe("once")
    expect(block.match_strategy).toBe("exactly_one")
    expect(block.rules.map(rule => rule.condition)).toEqual([
      { type: "predicate", fact: "aggregates.has_tiered_snvs", operator: "eq", value: true },
      { type: "predicate", fact: "aggregates.has_tiered_snvs", operator: "eq", value: false },
    ])
    expect(block.rules.every(rule => !rule.enabled)).toBe(true)
    expect(block.rules[0].rule_id).toBe("synthetic_base_snv_summary_reportable_snvs_present")
    expect(block.rules[0].output).toEqual([{ type: "renderer", name: "tier_summary" }])
    const next = sectionStarter([block], "snv_summary", scope)
    expect(new Set([...block.rules, ...next.rules].map(rule => rule.rule_id)).size).toBe(4)
    const identity = block.rules[0].rule_id
    block.rules[0].name = "Reviewed visible name"
    expect(block.rules[0].rule_id).toBe(identity)
  })
  it("builds disabled dynamic intro rules with optional heading and safe conditions", () => {
    const block = sectionStarter([], "intro", scope)
    expect(block.block_id).toBe("synthetic_base_intro")
    expect(block.show_heading).toBe(false)
    expect(block.match_strategy).toBe("all_matches")
    expect(block.rules).toHaveLength(5)
    expect(block.rules.every(rule => !rule.enabled)).toBe(true)
    expect(JSON.stringify(block)).toContain("asp.covered_genes_count")
    expect(JSON.stringify(block)).toContain("gene_lists.snv.names")
    expect(block.rules[2].condition).toMatchObject({ fact: "sample.paired", value: false })
    expect(block.rules[4].condition).toMatchObject({ type: "all", children: [{ fact: "sample.paired" }, { type: "not", child: { operator: "is_empty" } }] })
    const next = sectionStarter([block], "intro", scope)
    expect(next.block_id).not.toBe(block.block_id)
    expect(new Set([...block.rules, ...next.rules].map(rule => rule.rule_id)).size).toBe(10)
  })
  it("selects CNV findings and measurement collections explicitly", () => {
    const cnv = sectionStarter([], "cnv", scope)
    expect(cnv.analysis).toBe("CNV")
    expect(cnv.evaluation.mode).toBe("each_finding")
    expect(cnv.rules[0].condition).toMatchObject({ fact: "finding.kind", value: "cnv" })
    expect(sectionStarter([], "hrd", scope).evaluation).toEqual({ mode: "each_item", collection: "hrd" })
  })
})
