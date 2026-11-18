// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Surface } from "@/components/ui/surface"
import { Notice } from "@/components/ui/notice"
import { Button } from "@/components/ui/button"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { hasPermission, isSuperuser, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { fullDateTime } from "@/lib/detail-formatters"
import type { PasswordRecoveryRecord } from "@/lib/generated"

export function PasswordRecoveryPanel() {
  const { data: user } = useCurrentUserAccess()
  const allowed = hasPermission(user, "user:edit") && (isSuperuser(user) || Boolean(user?.roles?.includes("sys_admin")))
  const client = useQueryClient()
  const [selected, setSelected] = useState<PasswordRecoveryRecord | null>(null)
  const requests = useQuery({
    queryKey: ["password-recovery-requests", user?.username],
    queryFn: ({ signal }) => api.get<PasswordRecoveryRecord[]>("/users/password-recovery", { signal, errorNotice: "inline" }).then(result => result.data),
    enabled: allowed,
  })
  const complete = useMutation({
    mutationFn: (request: PasswordRecoveryRecord) => api.post(`/users/password-recovery/${encodeURIComponent(request.request_id)}/complete`, {}, { errorNotice: "inline" }),
    onSuccess: async () => {
      setSelected(null)
      await client.invalidateQueries({ queryKey: ["password-recovery-requests"] })
    },
  })
  if (!allowed) return null
  return <Surface as="section" variant="panel" className="space-y-3 p-3" aria-labelledby="password-recovery-title">
    <div className="flex items-center justify-between gap-3">
      <h2 id="password-recovery-title" className="text-base font-semibold">Password recovery</h2>
      <Button variant="outline" size="sm" disabled={requests.isFetching} onClick={() => void requests.refetch()}>Refresh</Button>
    </div>
    <p className="text-sm text-muted-foreground">Verify the account owner before acting. Reset LDAP passwords through your external directory service. For local accounts without email, associate a verified email in account administration and send a reset link. Coyote records completion; it does not reset LDAP passwords.</p>
    {requests.isPending && <p role="status">Loading recovery requests…</p>}
    {requests.isError && <Notice tone="danger">Unable to load recovery requests. Refresh to try again.</Notice>}
    {requests.data?.length === 0 && <p className="text-sm text-muted-foreground">No pending requests.</p>}
    {requests.data?.map(request => <div key={request.request_id} className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
      <div><p className="text-sm font-semibold">{request.username} · {request.provider.toUpperCase()}</p><p className="text-xs text-muted-foreground">Requested {fullDateTime(request.requested_at)}</p></div>
      <Button variant="outline" size="sm" onClick={() => { complete.reset(); setSelected(request) }}>Mark completed</Button>
    </div>)}
    <ConfirmationDialog open={Boolean(selected)} title="Confirm recovery completed" confirmLabel="Mark completed"
      description={<><p>Confirm that you verified {selected?.username} and completed their {selected?.provider.toUpperCase()} recovery outside this workflow. This records your name and the completion time and notifies the account owner. Do not enter or send passwords in Coyote.</p>{complete.isError && <Notice tone="danger">Unable to record completion. Retry or refresh the request list.</Notice>}</>}
      isPending={complete.isPending} onCancel={() => setSelected(null)} onConfirm={() => { if (selected) complete.mutate(selected) }} />
  </Surface>
}
