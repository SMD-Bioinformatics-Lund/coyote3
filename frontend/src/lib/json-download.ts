import { downloadText } from "@/lib/browser-download"

/** Download an application record without MongoDB implementation identifiers. */
export function withoutMongoIdentifiers(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withoutMongoIdentifiers)
  if (!value || typeof value !== "object") return value

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => key !== "_id")
      .map(([key, nested]) => [key, withoutMongoIdentifiers(nested)]),
  )
}

export function downloadJson(filename: string, value: unknown): void {
  downloadText(
    `${JSON.stringify(withoutMongoIdentifiers(value), null, 2)}\n`,
    filename.endsWith(".json") ? filename : `${filename}.json`,
    "application/json",
  )
}
