import { describe, expect, it } from "vitest"

import {
  filterFlags,
  findingRowClass,
  fusionCallers,
  fusionGenes,
  isFlaggedFinding,
  normalizedCallerList,
  selectedFusionCall,
  selectedTranslocationAnnotation,
  statusLabels,
  tierValue,
  translocationAlt,
  translocationGenes,
  translocationHgvs,
  translocationInfo,
  translocationPanelStatus,
  translocationPositionLabel,
  translocationType,
} from "./variant-helpers"

describe("variant display normalization", () => {
  it("detects disabled findings and composes their status labels", () => {
    const finding = {
      fp: true,
      blacklist: { reason: "panel artefact" },
      irrelevant: true,
      interesting: true,
      comments: [{ text: "reviewed" }],
    }
    expect(isFlaggedFinding(finding)).toBe(true)
    expect(statusLabels(finding)).toBe(
      "False positive | Blacklisted | Irrelevant | Interesting | Has comments",
    )
    expect(findingRowClass(finding)).toContain("opacity-60")
    expect(isFlaggedFinding({ blacklist: {}, override_blacklist: true })).toBe(false)
    expect(findingRowClass({})).toContain("hover:bg-primary")
  })

  it("normalizes tiers, flags, and callers", () => {
    expect(tierValue({ classification: { class: "2" }, tier: 4 })).toBe(2)
    expect(tierValue({ classification: { tier: 3 } })).toBe(3)
    expect(tierValue({ tier: "unknown" })).toBe(999)
    expect(filterFlags(["PASS,WARN", "", null, "FAIL"])).toEqual([
      "PASS",
      "WARN",
      "FAIL",
    ])
    expect(normalizedCallerList("freebayes, vardict & -")).toEqual(["freebayes", "vardict"])
    expect(normalizedCallerList(["manta", "", "-"])).toEqual(["manta"])
    expect(normalizedCallerList(["FusionCatcher", "fusioncatcher", "STARFUSION"])).toEqual([
      "FusionCatcher",
      "STARFUSION",
    ])
  })

  it("selects fusion calls and supports legacy fusion shapes", () => {
    const selected = { selected: true, caller: "arriba" }
    expect(selectedFusionCall({ calls: [{ caller: "star" }, selected] })).toBe(selected)
    expect(selectedFusionCall({ calls: [{ caller: "star" }] })).toEqual({ caller: "star" })
    expect(
      selectedFusionCall({
        frame: "in-frame",
        supporting_reads: { span: 12, split: 8 },
        breakpoints: ["1:10", "2:20"],
        callers: ["arriba", "star"],
      }),
    ).toMatchObject({
      effect: "in-frame",
      spanpairs: 12,
      spanreads: 8,
      breakpoint1: "1:10",
      breakpoint2: "2:20",
      caller: "arriba, star",
    })
    expect(fusionGenes({ genes: "BCR^ABL1" })).toEqual(["BCR", "ABL1"])
    expect(fusionGenes({ fusion_name: "EML4--ALK" })).toEqual(["EML4", "ALK"])
    expect(fusionGenes({})).toEqual([])
    expect(
      fusionCallers({ calls: [{ caller: "arriba" }, { caller: "arriba" }, { caller: "star" }] }),
    ).toBe("arriba, star")
    expect(fusionCallers({ callers: ["manta", "gridss"] })).toBe("manta, gridss")
    expect(fusionCallers({})).toBe("-")
  })

  it("normalizes translocation annotations, genes, and HGVS fields", () => {
    const mane = { Gene_Name: "BCR&ABL1", HGVSc: "c.1A>G", HGVSp: "p.X1Y" }
    const translocation = { INFO: [{ MANE_ANN: [mane], SVTYPE: "BND", PANEL: "IN" }] }
    expect(translocationInfo(translocation)).toEqual(translocation.INFO[0])
    expect(selectedTranslocationAnnotation(translocation)).toBe(mane)
    expect(translocationGenes(translocation)).toEqual(["BCR", "ABL1"])
    expect(translocationHgvs(mane)).toEqual({ coding: "c.1A>G", protein: "p.X1Y" })
    expect(translocationType(translocation)).toBe("BND")
    expect(translocationPanelStatus(translocation)).toBe("Yes")

    expect(translocationGenes({ genes: "ETV6;RUNX1" })).toEqual(["ETV6", "RUNX1"])
    expect(translocationGenes({ gene1: "KMT2A", gene2: "AFF1" })).toEqual(["KMT2A", "AFF1"])
    expect(selectedTranslocationAnnotation({ ANN: { Gene: "TP53" } })).toEqual({ Gene: "TP53" })
    expect(translocationType({ INFO: { ANN: [{ Annotation: ["fusion", "bidirectional"] }] } })).toBe(
      "fusion, bidirectional",
    )
  })

  it("formats panel state and breakpoint positions across source shapes", () => {
    expect(translocationPanelStatus({ panel: true })).toBe("Yes")
    expect(translocationPanelStatus({ panel: false })).toBe("No")
    expect(translocationPanelStatus({ panel: "OUT" })).toBe("No")
    expect(translocationPanelStatus({ panel: "review" })).toBe("review")
    expect(translocationPanelStatus({})).toBe("-")

    expect(translocationAlt({ ALT: ["N]2:20]"] })).toBe("N]2:20]")
    expect(translocationPositionLabel({ CHROM: "1", POS: 10, ALT: "N]2:20]" })).toBe(
      "1:10 N]2:20]",
    )
    expect(translocationPositionLabel({ chrom: "1", pos: 10, chrom2: "2", end: 20 })).toBe(
      "1:10 2:20",
    )
    expect(translocationPositionLabel({ POS: 10 })).toBe("10")
  })
})
