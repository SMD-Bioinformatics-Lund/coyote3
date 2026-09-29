export function readFormPath(source: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((value, key) => (
    value && typeof value === "object" ? (value as Record<string, unknown>)[key] : undefined
  ), source)
}

export function writeFormPath(source: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const result = structuredClone(source)
  const keys = path.split(".")
  let target = result
  for (const key of keys.slice(0, -1)) {
    const child = target[key]
    target[key] = child && typeof child === "object" && !Array.isArray(child) ? child : {}
    target = target[key] as Record<string, unknown>
  }
  target[keys[keys.length - 1]] = value
  return result
}
