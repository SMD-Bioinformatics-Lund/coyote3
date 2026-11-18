// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { isSuperuser, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { icon } from "@/lib/assets"
import { SESSION_ACTIVITY_REFRESH_INTERVAL_MS } from "@/lib/defaults"
import { fullDateTime } from "@/lib/detail-formatters"
import type { SessionActivitySummary } from "@/lib/generated"
import { RuntimeMetric } from "../runtime-panels"

export function SessionActivityPanel() {
  const { data: user } = useCurrentUserAccess()
  const allowed = isSuperuser(user)
  const activity = useQuery({
    queryKey: ["admin-session-activity", user?.username],
    queryFn: ({ signal }) => api.get<SessionActivitySummary>("/users/session-activity", {
      signal,
      errorNotice: "inline",
    }).then(response => response.data),
    enabled: allowed,
    retry: false,
    staleTime: SESSION_ACTIVITY_REFRESH_INTERVAL_MS,
    refetchInterval: query => query.state.error ? false : SESSION_ACTIVITY_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  if (!allowed) return null

  return (
    <Surface as="section" variant="panel" aria-labelledby="session-activity-title" className="p-3">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 id="session-activity-title" className="text-base font-semibold">Login activity</h2>
          <p className="text-xs text-muted-foreground">
            Counts valid sign-ins. Closing a browser may leave a session signed in until it expires.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void activity.refetch()} disabled={activity.isFetching}>
          <icon.refreshCw className="h-4 w-4" />Refresh
        </Button>
      </div>
      {activity.isError ? (
        <p role="alert" className="text-sm text-destructive">Login activity is unavailable. Refresh to try again.</p>
      ) : activity.isPending ? (
        <p role="status" className="text-sm text-muted-foreground">Loading login activity…</p>
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-3">
            <RuntimeMetric label="Signed-in users" value={activity.data.signed_in_users}
              description="Distinct enabled accounts with at least one valid, unexpired login session. Multiple sessions count as one user." />
            <RuntimeMetric label="Valid sessions" value={activity.data.active_sessions}
              description="Unexpired login sessions whose accounts and credentials are still valid. One user may have several sessions." />
            <RuntimeMetric label="Recently active users" value={activity.data.recently_active_users}
              description={`Signed-in users with an authenticated request in the last ${activity.data.recent_activity_seconds / 60} minutes. Background requests count as activity; this does not confirm someone is at the screen.`} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Updated {fullDateTime(activity.data.observed_at)}. Refreshes every {SESSION_ACTIVITY_REFRESH_INTERVAL_MS / 1000} seconds while this page is visible.
          </p>
        </>
      )}
    </Surface>
  )
}
