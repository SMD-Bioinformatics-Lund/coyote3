import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Activity, KeyRound, User } from "lucide-react"
import { api } from "@/lib/api"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

export function Profile() {
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [message, setMessage] = useState("")

  const { data, isLoading, error } = useQuery({
    queryKey: ["auth-session"],
    queryFn: () => api.get("/auth/session").then((res) => res.data),
  })

  const changePassword = useMutation({
    mutationFn: () => api.post("/auth/password/change", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
    onSuccess: () => {
      setCurrentPassword("")
      setNewPassword("")
      setMessage("Password changed.")
      notifySuccess("Password changed", "Your local password was updated.", "Profile")
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : "Unable to change password.")
      notifyActionError("Unable to change password", err, "Profile")
    },
  })

  const user = data?.user ?? {}
  const effectiveRole = user.role || user.primary_role || "Authenticated"
  const assignedRoles = Array.isArray(user.roles) && user.roles.length
    ? user.roles
    : (user.role || user.primary_role ? [user.role || user.primary_role] : [])

  return (
    <PageShell
      eyebrow="Account"
      title="Profile"
      description="View your active session and manage your local account password."
    >
      {isLoading ? (
        <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load profile"}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_26rem]">
          <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-xl bg-primary/10 p-3 text-primary">
                <User className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold">{data?.user?.username || "Current user"}</h2>
                <p className="text-sm text-muted-foreground">{effectiveRole}</p>
              </div>
            </div>
            <dl className="grid gap-3 rounded-lg border border-border bg-muted/20 p-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Username</dt>
                <dd className="mt-1 font-semibold">{data?.user?.username || data?.user?._id || "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Email</dt>
                <dd className="mt-1 font-semibold">{data?.user?.email || "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Highest role</dt>
                <dd className="mt-1 font-semibold">{effectiveRole}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Access level</dt>
                <dd className="mt-1 font-semibold">{data?.user?.access_level ?? "-"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Assigned roles</dt>
                <dd className="mt-2 flex flex-wrap gap-2">
                  {assignedRoles.length ? assignedRoles.map((role: string) => (
                    <label
                      key={role}
                      className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold"
                    >
                      <input type="checkbox" checked readOnly className="h-3.5 w-3.5 accent-primary" />
                      {role}
                    </label>
                  )) : (
                    <span className="text-sm text-muted-foreground">No roles assigned</span>
                  )}
                </dd>
              </div>
            </dl>
          </section>

          <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-primary" />
              <h2 className="font-bold">Change Password</h2>
            </div>
            <div className="space-y-3">
              <label className="block text-sm font-semibold">
                Current password
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm font-semibold">
                New password
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
              <button
                onClick={() => changePassword.mutate()}
                disabled={!currentPassword || !newPassword || changePassword.isPending}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
              >
                {changePassword.isPending && <Activity className="h-4 w-4 animate-spin" />}
                Update password
              </button>
              {message && <p className="text-sm text-muted-foreground">{message}</p>}
            </div>
          </section>
        </div>
      )}
    </PageShell>
  )
}
