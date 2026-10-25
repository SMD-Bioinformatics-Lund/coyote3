export type DatabaseLogo = {
  src: string
  alt: string
}

const DATABASE_LOGOS: Array<{ matches: string[]; logo: DatabaseLogo }> = [
  {
    matches: ["brca_exchange", "brcaexchange"],
    logo: { src: "/logos/brca-exchange-vector.svg", alt: "BRCA Exchange logo" },
  },
  {
    matches: ["civic"],
    logo: { src: "/logos/civic-vector.svg", alt: "CIViC logo" },
  },
  {
    matches: ["clinpgx", "pharmgkb"],
    logo: { src: "/logos/clinpgx-vector.svg", alt: "ClinPGx logo" },
  },
  {
    matches: ["cosmic"],
    logo: { src: "/logos/cosmic-vector.svg", alt: "COSMIC logo" },
  },
  {
    matches: ["oncokb"],
    logo: { src: "/logos/oncokb-vector.svg", alt: "OncoKB logo" },
  },
  {
    matches: ["cpic"],
    logo: { src: "/logos/cpic-vector.svg", alt: "CPIC logo" },
  },
]

export function databaseLogo(source: string): DatabaseLogo | undefined {
  const normalized = String(source || "").trim().toLocaleLowerCase().replaceAll(/[-\s]+/g, "_")
  return DATABASE_LOGOS.find(({ matches }) => matches.some((name) => normalized.includes(name)))?.logo
}
