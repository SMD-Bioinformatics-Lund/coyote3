import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import {
  CallerBadges,
  ConsequenceBadges,
  FilterFlagBadges,
  ImpactBadge,
  InfoTooltipBadge,
  PredictionBadge,
  StatusBadges,
  TierBadge,
} from "./variant-ui"

describe("variant UI semantics", () => {
  it.each([
    [1, "Tier I", "Stark klinisk signifikans"],
    [2, "Tier II", "Potentiell klinisk signifikans"],
    [3, "Tier III", "Oklar klinisk signifikans"],
    [4, "Tier IV", "Benign/sannolikt benign"],
    [7, "Tier 7", "Classification"],
  ])("describes tier %s", (tier, heading, description) => {
    render(<TierBadge tier={tier} />)
    fireEvent.focus(screen.getByText(String(tier)))
    expect(screen.getByText(heading)).toBeInTheDocument()
    expect(screen.getByText(description)).toBeInTheDocument()
  })

  it("renders a placeholder for missing and sentinel tiers", () => {
    const { rerender } = render(<TierBadge tier={undefined} />)
    expect(screen.getByText("-")).toBeInTheDocument()
    rerender(<TierBadge tier={999} />)
    expect(screen.getByText("-")).toBeInTheDocument()
  })

  it("renders all finding state and knowledgebase markers", () => {
    render(
      <StatusBadges
        finding={{
          fp: true,
          blacklist: true,
          override_blacklist: true,
          irrelevant: true,
          interesting: true,
          comments: [{ text: "reviewed" }],
        }}
        gene="TP53"
        hasOncoKbCancerGene
        hasOncoKbActionable
        hasClinPgxGene
        clinPgxRecord={{ pharmgkb_accession_id: "PA123", has_cpic_dosing_guideline: true }}
      />,
    )

    for (const name of [
      "False positive",
      "Blacklist override",
      "Irrelevant",
      "Interesting",
      "Has comments",
      "OncoKB public cancer gene",
      "Historical local OncoKB actionable evidence",
      "ClinPGx gene",
    ]) {
      expect(screen.getByLabelText(name)).toBeInTheDocument()
    }
    expect(screen.queryByLabelText("Blacklisted")).not.toBeInTheDocument()
    expect(screen.getByLabelText("OncoKB public cancer gene")).toHaveAttribute("target", "_blank")
    expect(screen.getByLabelText("ClinPGx gene")).toHaveAttribute("href", expect.stringContaining("PA123"))
  })

  it("shows blacklist and ClinPGx variant annotation states", () => {
    const { rerender } = render(<StatusBadges finding={{ blacklisted: true }} />)
    fireEvent.mouseEnter(screen.getByLabelText("Blacklisted"))
    expect(screen.getByText("This finding matches the center blacklist.", { exact: false })).toBeInTheDocument()

    rerender(
      <StatusBadges
        finding={{}}
        gene="CYP2D6"
        hasClinPgxGene
        clinPgxRecord={{ has_variant_annotation: true }}
      />,
    )
    fireEvent.focus(screen.getByLabelText("ClinPGx gene"))
    expect(screen.getByText("ClinPGx variant annotation")).toBeInTheDocument()
  })

  it("renders linked and unlinked informational badges with tooltip context", () => {
    const { rerender } = render(
      <InfoTooltipBadge label="MANE Select" description="Preferred transcript">MANE</InfoTooltipBadge>,
    )
    fireEvent.focus(screen.getByLabelText("MANE Select"))
    expect(screen.getByText("Transcript marker")).toBeInTheDocument()
    expect(screen.getByText("Preferred transcript")).toBeInTheDocument()

    rerender(
      <InfoTooltipBadge label="Reference" description="External reference" href="https://example.test">
        REF
      </InfoTooltipBadge>,
    )
    expect(screen.getByRole("link", { name: "Reference" })).toHaveAttribute("href", "https://example.test")
  })

  it("normalizes, de-duplicates, hides, and describes filter flags", () => {
    render(
      <FilterFlagBadges
        value="PASS,WARN_LOW_QUAL,FAIL_LOW_QUAL,CUSTOM,HIDDEN"
        metadata={{
          exact: {
            FAIL_LOW_QUAL: { label: "Quality", severity: "fail", description: "Insufficient quality." },
            CUSTOM: { label: "Custom review", severity: "info", description: "Center review rule." },
            HIDDEN: { hidden: true },
          },
          prefixes: {
            WARN_: { label: "Quality", severity: "warn", description: "Quality warning." },
          },
        }}
      />,
    )

    expect(screen.getByText("PASS")).toBeInTheDocument()
    expect(screen.getByText("Quality")).toBeInTheDocument()
    expect(screen.getByText("Custom review")).toBeInTheDocument()
    expect(screen.queryByText("HIDDEN")).not.toBeInTheDocument()
    expect(screen.getAllByText("Quality")).toHaveLength(1)

    fireEvent.focus(screen.getByText("Quality"))
    expect(screen.getByText("FAIL_LOW_QUAL")).toBeInTheDocument()
    expect(screen.getByText("Insufficient quality.")).toBeInTheDocument()
  })

  it("omits unknown unconfigured flags and handles an empty flag list", () => {
    const { rerender } = render(<FilterFlagBadges value="UNRECOGNIZED" />)
    expect(screen.getByText("-")).toBeInTheDocument()
    rerender(<FilterFlagBadges value={null} />)
    expect(screen.getByText("-")).toBeInTheDocument()
  })

  it.each([
    ["HIGH", "High predicted consequence"],
    ["MODERATE", "Moderate predicted consequence"],
    ["LOW", "Low predicted consequence"],
    ["MODIFIER", "Modifier consequence"],
    ["OTHER", "No VEP impact description"],
  ])("explains %s VEP impact", (impact, description) => {
    render(<ImpactBadge value={impact} />)
    fireEvent.focus(screen.getByText(impact))
    expect(screen.getAllByText(description, { exact: false }).length).toBeGreaterThan(0)
  })

  it.each([
    ["deleterious(0.01)", "Deleterious", "SIFT predicts"],
    ["probably_damaging(0.99)", "Damaging", "PolyPhen predicts a probably damaging"],
    ["possibly_damaging", "Possibly damaging", "possible damaging effect"],
    ["low_confidence", "Low confidence", "low confidence"],
    ["tolerated", "Tolerated", "likely tolerated"],
    ["benign", "Benign", "benign protein effect"],
    ["unclassified", "Prediction", "supporting evidence only"],
  ])("explains prediction %s", (value, label, description) => {
    render(<PredictionBadge value={value} />)
    fireEvent.focus(screen.getByText(value))
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getAllByText(description, { exact: false }).length).toBeGreaterThan(0)
  })

  it("renders caller names and no placeholder for an empty caller list", () => {
    const { rerender, container } = render(<CallerBadges value="freebayes,TNSCOPE,freebayes" />)
    expect(screen.getByText("freebayes")).toBeInTheDocument()
    expect(screen.getAllByText("freebayes")).toHaveLength(1)
    expect(screen.getByText("TNSCOPE")).toBeInTheDocument()
    rerender(<CallerBadges value={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("uses VEP translations for consequence display and tooltip content", () => {
    render(
      <ConsequenceBadges
        value={["missense_variant", "intron_variant"]}
        translations={{
          missense_variant: { label: "Missense", description: "Protein sequence change.", impact: "MODERATE" },
          intron_variant: { display_name: "Intron", definition: "Located in an intron.", IMPACT: "MODIFIER" },
        }}
      />,
    )
    expect(screen.getByText("Missense")).toBeInTheDocument()
    expect(screen.getByText("Intron")).toBeInTheDocument()
    fireEvent.focus(screen.getByText("Missense"))
    expect(screen.getByText("missense_variant")).toBeInTheDocument()
    expect(screen.getByText("Protein sequence change.")).toBeInTheDocument()
    expect(screen.getByText("MODERATE")).toBeInTheDocument()
  })

  it("supports comma-separated raw consequence labels and empty values", () => {
    const { rerender } = render(<ConsequenceBadges value="splice_acceptor_variant,intron_variant" compact={false} />)
    expect(screen.getByText("splice_acceptor_variant")).toBeInTheDocument()
    expect(screen.getByText("intron_variant")).toBeInTheDocument()
    rerender(<ConsequenceBadges value="" />)
    expect(screen.getByText("-")).toBeInTheDocument()
  })
})
