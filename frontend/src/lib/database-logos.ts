import { logo, type ImageAsset } from "@/lib/assets"

export type DatabaseLogo = ImageAsset

const DATABASE_LOGOS: Array<{ matches: string[]; logo: DatabaseLogo }> = [
  {
    matches: ["brca_exchange", "brcaexchange"],
    logo: logo.brcaExchange,
  },
  {
    matches: ["civic"],
    logo: logo.civic,
  },
  {
    matches: ["clinpgx", "pharmgkb"],
    logo: logo.clinpgx,
  },
  {
    matches: ["cosmic"],
    logo: logo.cosmic,
  },
  {
    matches: ["oncokb"],
    logo: logo.oncokb,
  },
  {
    matches: ["cpic"],
    logo: logo.cpic,
  },
]

export function databaseLogo(source: string): DatabaseLogo | undefined {
  const normalized = String(source || "").trim().toLocaleLowerCase().replaceAll(/[-\s]+/g, "_")
  return DATABASE_LOGOS.find(({ matches }) => matches.some((name) => normalized.includes(name)))?.logo
}
