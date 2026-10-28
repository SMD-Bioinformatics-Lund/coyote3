export type ResourceNames = {
  name?: string | null
  display_name?: string | null
  displayname?: string | null
}

/** Compact labels for tables, dropdowns, filters and linked badges. */
export function shortResourceName(resource: ResourceNames | undefined, identifier: string) {
  return resource?.name?.trim() || resource?.display_name?.trim()
    || resource?.displayname?.trim() || identifier
}

/** Explain the naming convention without changing persisted resource identifiers. */
export function resourceNameHint(field: string) {
  if (field === "name") return "Short name used in tables, dropdowns, filters and compact badges. Use Display name for the full name shown on cards."
  if (field === "display_name" || field === "displayname") return "Full name shown on cards and detail headings. Tables, dropdowns and filters prefer Name; this full name is the fallback when no short name is set."
  return undefined
}
