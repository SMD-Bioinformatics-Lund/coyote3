import { expect, it } from "vitest"
import { matchedKnowledgebaseGenes } from "./knowledgebase-markers"
import { isOncoKbGene } from "./oncokb-ui"

it("only matches genes owned by the knowledgebase result", () => {
  const records = Object.create({ SYNTHETIC: { name: "inherited" } })
  expect(matchedKnowledgebaseGenes(["SYNTHETIC", "constructor"], records)).toEqual([])
  expect(isOncoKbGene("SYNTHETIC", records)).toBe(false)
  expect(isOncoKbGene("constructor", {})).toBe(false)
  expect(isOncoKbGene("SYNTHETIC", { SYNTHETIC: {} })).toBe(true)
})
