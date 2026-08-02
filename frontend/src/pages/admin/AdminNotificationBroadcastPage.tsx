import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Megaphone, Search, Send } from "lucide-react"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

type Recipient = { username: string; name: string; email: string }
type RecipientRole = { role_id: string; label: string; user_count: number }
type RecipientOptions = { users: Recipient[]; roles: RecipientRole[] }
type Audience = "all" | "roles" | "selected"
type Tone = "info" | "success" | "warning" | "error"
type Category = "application" | "feature" | "maintenance" | "security" | "warning"

export function AdminNotificationBroadcastPage() {
  const [audience, setAudience] = useState<Audience>("all")
  const [recipients, setRecipients] = useState<string[]>([])
  const [roleIds, setRoleIds] = useState<string[]>([])
  const [tone, setTone] = useState<Tone>("info")
  const [category, setCategory] = useState<Category>("application")
  const [title, setTitle] = useState("")
  const [message, setMessage] = useState("")
  const [search, setSearch] = useState("")
  const [confirming, setConfirming] = useState(false)

  const recipientQuery = useQuery({
    queryKey: ["notification-broadcast-recipients"],
    queryFn: () => api.get<RecipientOptions>("/admin/notifications/recipients").then((response) => response.data),
  })
  const filteredRecipients = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (recipientQuery.data?.users || []).filter((user) =>
      !needle || [user.username, user.name, user.email].some((value) => value.toLowerCase().includes(needle))
    )
  }, [recipientQuery.data, search])

  const mutation = useMutation({
    mutationFn: () => api.post<{ recipient_count: number }>("/admin/notifications/broadcast", {
      audience,
      recipients: audience === "selected" ? recipients : [],
      role_ids: audience === "roles" ? roleIds : [],
      tone,
      category,
      title: title.trim(),
      message: message.trim(),
    }),
    onSuccess: (response) => {
      notifySuccess("Notification sent", `Published to ${response.data.recipient_count} active user(s).`)
      setTitle("")
      setMessage("")
      setRecipients([])
      setRoleIds([])
      setConfirming(false)
    },
    onError: (error) => notifyActionError("Unable to send notification", error),
  })

  const valid = title.trim().length >= 3 && message.trim().length > 0 && (
    audience === "all" || (audience === "roles" ? roleIds.length > 0 : recipients.length > 0)
  )

  return (
    <PageShell
      eyebrow="Admin"
      title="Broadcast Notifications"
      description="Publish application information, feature notices, maintenance messages, warnings, or security notices to active accounts."
      actions={<Button onClick={() => setConfirming(true)} disabled={!valid || mutation.isPending}><Send className="h-4 w-4" />Send</Button>}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <section className="surface-panel space-y-4 p-4">
          <div className="flex items-center gap-2">
            <span className="rounded-lg bg-primary/10 p-2 text-primary"><Megaphone className="h-4 w-4" /></span>
            <div><h2 className="font-bold">Message</h2><p className="text-sm text-muted-foreground">The title and message are retained in each recipient's notification inbox.</p></div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label htmlFor="notification-category">Category</Label><select id="notification-category" className="paper-inset h-9 w-full rounded-lg px-2.5 text-sm" value={category} onChange={(event) => setCategory(event.target.value as Category)}><option value="application">Application</option><option value="feature">Feature</option><option value="maintenance">Maintenance</option><option value="security">Security</option><option value="warning">Warning</option></select></div>
            <div className="space-y-1.5"><Label htmlFor="notification-tone">Severity</Label><select id="notification-tone" className="paper-inset h-9 w-full rounded-lg px-2.5 text-sm" value={tone} onChange={(event) => setTone(event.target.value as Tone)}><option value="info">Information</option><option value="success">Success</option><option value="warning">Warning</option><option value="error">Critical</option></select></div>
          </div>
          <div className="space-y-1.5"><Label htmlFor="notification-title">Title</Label><Input id="notification-title" maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Scheduled maintenance" /></div>
          <div className="space-y-1.5"><Label htmlFor="notification-message">Message</Label><textarea id="notification-message" className="paper-inset min-h-36 w-full rounded-lg p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/35" maxLength={5000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Describe the information and any action users need to take." /></div>
        </section>

        <section className="surface-panel p-4">
          <h2 className="font-bold">Recipients</h2>
          <p className="mt-1 text-sm text-muted-foreground">Only active accounts can receive a selected-user broadcast.</p>
          <div className="mt-3 grid grid-cols-3 rounded-lg border border-border bg-muted p-1">
            {(["all", "roles", "selected"] as Audience[]).map((option) => <button key={option} type="button" onClick={() => setAudience(option)} className={`rounded-md px-3 py-2 text-xs font-bold ${audience === option ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>{option === "all" ? "All users" : option === "roles" ? "By role" : "Individuals"}</button>)}
          </div>
          {audience === "roles" && <div className="mt-3 max-h-80 space-y-1 overflow-auto rounded-lg border border-border bg-background p-2">
            {(recipientQuery.data?.roles || []).map((role) => <label key={role.role_id} className="flex cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-2 hover:bg-muted"><span className="flex items-center gap-2"><input type="checkbox" checked={roleIds.includes(role.role_id)} onChange={(event) => setRoleIds((current) => event.target.checked ? [...current, role.role_id] : current.filter((item) => item !== role.role_id))} /><span className="text-sm font-bold">{role.label}</span></span><span className="text-xs text-muted-foreground">{role.user_count} active</span></label>)}
            {!recipientQuery.isLoading && !(recipientQuery.data?.roles || []).length && <p className="p-3 text-sm text-muted-foreground">No active roles have recipients.</p>}
          </div>}
          {audience === "selected" && <div className="mt-3">
            <div className="relative"><Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input className="pl-8" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search users" /></div>
            <div className="mt-2 max-h-80 space-y-1 overflow-auto rounded-lg border border-border bg-background p-2">
              {filteredRecipients.map((user) => <label key={user.username} className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-2 hover:bg-muted"><input type="checkbox" className="mt-0.5" checked={recipients.includes(user.username)} onChange={(event) => setRecipients((current) => event.target.checked ? [...current, user.username] : current.filter((item) => item !== user.username))} /><span className="min-w-0"><span className="block text-sm font-bold">{user.name || user.username}</span><span className="block truncate text-xs text-muted-foreground">{user.username}{user.email ? ` · ${user.email}` : ""}</span></span></label>)}
              {!recipientQuery.isLoading && !filteredRecipients.length && <p className="p-3 text-sm text-muted-foreground">No active users match this search.</p>}
            </div>
            <p className="mt-2 text-xs font-bold text-muted-foreground">{recipients.length} selected</p>
          </div>}
        </section>
      </div>
      <ConfirmationDialog open={confirming} title="Send notification?" description={audience === "all" ? "This message will be visible to every active user." : audience === "roles" ? `This message will be sent to active users in ${roleIds.length} selected role(s).` : `This message will be visible to ${recipients.length} selected user(s).`} confirmLabel="Send notification" isPending={mutation.isPending} onConfirm={() => mutation.mutate()} onCancel={() => setConfirming(false)} />
    </PageShell>
  )
}
