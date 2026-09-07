export type TierLabel = {
  roman: string
  short: string
  description: string
}

export const TIER_LABELS: Record<number, TierLabel> = {
  1: {
    roman: "I",
    short: "Strong clinical significance",
    description: "Variant of strong clinical significance.",
  },
  2: {
    roman: "II",
    short: "Potential clinical significance",
    description: "Variant of potential clinical significance.",
  },
  3: {
    roman: "III",
    short: "Uncertain clinical significance",
    description: "Variant of uncertain clinical significance.",
  },
  4: {
    roman: "IV",
    short: "Benign / likely benign",
    description: "Variant assessed as benign or likely benign.",
  },
}
