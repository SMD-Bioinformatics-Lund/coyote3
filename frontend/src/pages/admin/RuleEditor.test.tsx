import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { sectionStarter } from "./clinical-rule-authoring"
import { RuleEditor } from "./RuleEditor"
import { matchingConditionPreset } from "./rule-condition-presets"

const block = sectionStarter([], "snv", { asp_id: "synthetic", diagnosis_id: "base", analyte: "dna", language: "sv", name: "Synthetic" })
block.evaluation = { mode: "once", collection: null }
const rule = { ...block.rules[0], condition: null, output: [{ type: "renderer" as const, name: "tier_summary" as const }] }

describe("Grouped SNV sentences", () => {
  it("offers a valid selected-list count without asking users to assemble nested conditions", () => {
    const change = vi.fn()
    const facts = [{ path: "item.selected_for", label: "Gene list selected analyses", group: "Current gene list", kind: "string_list" as const, operators: ["contains"], scopes: ["each_item"] }]
    render(<RuleEditor rule={rule} block={block} facts={facts} controlledValues={{}} change={change} />)
    fireEvent.change(screen.getByLabelText("Start with a common scenario"), { target: { value: "selected_snv_lists" } })
    expect(change).toHaveBeenCalledWith(expect.objectContaining({ condition: {
      type: "collection_match", collection: "applied_gene_lists", quantifier: "count",
      count: { operator: "gte", value: 1 },
      where: { type: "predicate", fact: "item.selected_for", operator: "contains", value: "snv" },
    }, output: rule.output }))
    expect(matchingConditionPreset({ where: { type: "predicate", fact: "item.selected_for", operator: "contains", value: "snv" }, count: { value: 1, operator: "gte" }, collection: "applied_gene_lists", type: "collection_match", quantifier: "count" }, facts)?.key).toBe("selected_snv_lists")
  })

  it("opens question-mark guidance with a click", () => {
    render(<RuleEditor rule={rule} block={block} facts={[]} controlledValues={{}} change={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: "Help: Choose when to include a sentence" }))
    expect(screen.getByRole("tooltip")).toHaveTextContent("A preset replaces this rule’s existing condition, not its text")
    fireEvent.keyDown(screen.getByRole("button", { name: "Help: Choose when to include a sentence" }), { key: "Escape" })
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })
  it("offers sentence insertion directly without requiring the advanced parts editor", () => {
    const insert = vi.fn()
    render(<RuleEditor rule={rule} block={block} facts={[]} controlledValues={{}} change={vi.fn()} sentenceTerminology={{ tier_summary: { first_prefix: "Vid analysen finner man " } }} useTierSentences={insert} />)
    fireEvent.click(screen.getByRole("button", { name: "Use grouped SNV sentences" }))
    expect(insert).toHaveBeenCalledOnce()
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
  })

  it("lets an existing renderer receive missing wording without replacing its text", () => {
    const change = vi.fn()
    const terms = { first_prefix: "Vid analysen finner man " }
    render(<RuleEditor rule={rule} block={block} facts={[]} controlledValues={{}} change={vi.fn()} terminology={{ existing: "Preserve" }} sentenceTerminology={{ tier_summary: terms }} changeTerminology={change} />)
    fireEvent.click(screen.getByText("Edit tier summary wording"))
    fireEvent.click(screen.getByRole("button", { name: "Add Swedish sentence wording" }))
    expect(change).toHaveBeenCalledWith({ existing: "Preserve", tier_summary: terms })
  })

  it("does not offer a Swedish fallback for a language without sentence wording", () => {
    render(<RuleEditor rule={rule} block={block} facts={[]} controlledValues={{}} change={vi.fn()} useTierSentences={vi.fn()} changeTerminology={vi.fn()} />)
    expect(screen.queryByRole("button", { name: "Use grouped SNV sentences" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Add Swedish sentence wording" })).not.toBeInTheDocument()
  })

  it("preserves the imported CNV renderer and lets its wording be added for review", () => {
    const change = vi.fn()
    const terms = { first_prefix: "Vid analysen finner man en " }
    const cnvRule = { ...rule, output: [{ type: "renderer" as const, name: "cnv_summary" as const }] }
    render(<RuleEditor rule={cnvRule} block={{ ...block, analysis: "CNV" }} facts={[]} controlledValues={{}} change={vi.fn()} terminology={{ existing: "Preserve" }} sentenceTerminology={{ cnv_summary: terms }} changeTerminology={change} />)
    expect(screen.getByLabelText("Report sentence")).toHaveValue("{{renderer:cnv_summary}}")
    fireEvent.click(screen.getByText("Advanced output parts and formatting"))
    expect(screen.getByRole("option", { name: "Grouped CNV summary" })).toHaveProperty("selected", true)
    fireEvent.click(screen.getByText("Edit cnv summary wording"))
    fireEvent.click(screen.getByRole("button", { name: "Add Swedish sentence wording" }))
    expect(change).toHaveBeenCalledWith({ existing: "Preserve", cnv_summary: terms })
  })
})
