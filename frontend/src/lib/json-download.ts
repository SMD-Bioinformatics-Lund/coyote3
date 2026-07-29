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
  const blob = new Blob([`${JSON.stringify(withoutMongoIdentifiers(value), null, 2)}\n`], {
    type: "application/json",
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename.endsWith(".json") ? filename : `${filename}.json`
  link.click()
  URL.revokeObjectURL(url)
}
