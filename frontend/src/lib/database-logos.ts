export type DatabaseLogo = {
  src: string
  alt: string
}

const DATABASE_LOGOS: Array<{ matches: string[]; logo: DatabaseLogo }> = [
  {
    matches: ["brca_exchange", "brcaexchange"],
    logo: { src: "/BRCA-Exchange.png", alt: "BRCA Exchange logo" },
  },
  {
    matches: ["civic"],
    logo: { src: "/civic.png", alt: "CIViC logo" },
  },
  {
    matches: ["clinpgx", "pharmgkb"],
    logo: { src: "/clinPGxpng.png", alt: "ClinPGx logo" },
  },
  {
    matches: ["cosmic"],
    logo: { src: "/COSMIC.png", alt: "COSMIC logo" },
  },
  {
    matches: ["oncokb"],
    logo: { src: "/OncoKB.png", alt: "OncoKB logo" },
  },
  {
    matches: ["cpic"],
    logo: { src: "/cpic.svg", alt: "CPIC logo" },
  },
]

export function databaseLogo(source: string): DatabaseLogo | undefined {
  const normalized = String(source || "").trim().toLocaleLowerCase().replaceAll(/[-\s]+/g, "_")
  return DATABASE_LOGOS.find(({ matches }) => matches.some((name) => normalized.includes(name)))?.logo
}
