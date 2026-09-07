import type { QueryClient } from "@tanstack/react-query"

export const SESSION_CHANGED_EVENT = "coyote3:session-changed"

export async function clearSessionState(client: QueryClient) {
  await client.cancelQueries()
  client.clear()
  for (const storageName of ["localStorage", "sessionStorage"] as const) {
    try {
      const storage = window[storageName]
      for (const key of Object.keys(storage)) {
        if (key.startsWith("coyote3.notifications:") || key.startsWith("coyote3.table.")) {
          storage.removeItem(key)
        }
      }
    } catch {
      // Browser storage may be disabled; in-memory session isolation still applies.
    }
  }
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT))
}
