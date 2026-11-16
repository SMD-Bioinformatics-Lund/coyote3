// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { QueryClient } from "@tanstack/react-query"

export const SESSION_CHANGED_EVENT = "coyote4:session-changed"
export const NOTIFICATION_STORAGE_PREFIX = "coyote4:notification-tray:"

export async function clearSessionState(client: QueryClient) {
  await client.cancelQueries()
  client.clear()
  for (const storageName of ["localStorage", "sessionStorage"] as const) {
    try {
      const storage = window[storageName]
      for (const key of Object.keys(storage)) {
        if (key.startsWith(NOTIFICATION_STORAGE_PREFIX) || key.startsWith("coyote4.table.")) {
          storage.removeItem(key)
        }
      }
    } catch {
      // Browser storage may be disabled; in-memory session isolation still applies.
    }
  }
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT))
}
