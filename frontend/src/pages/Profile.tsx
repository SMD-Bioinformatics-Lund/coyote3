import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Activity, BadgeCheck, Dna, KeyRound, Mail, ShieldCheck, User } from "lucide-react"
import { api } from "@/lib/api"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

export function Profile() {
  const queryClient = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [message, setMessage] = useState("")
  const [profileDraft, setProfileDraft] = useState({ firstname: "", lastname: "", fullname: "", job_title: "" })

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
  useEffect(() => {
    if (!data?.user) return
    setProfileDraft({
      firstname: data.user.firstname || "",
      lastname: data.user.lastname || "",
      fullname: data.user.fullname || "",
      job_title: data.user.job_title || "",
    })
  }, [data?.user])
  const updateProfile = useMutation({
    mutationFn: () => api.patch("/auth/profile", profileDraft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth-session"] })
      notifySuccess("Profile updated", "Your account details were saved.", "Profile")
    },
    onError: (err) => notifyActionError("Unable to update profile", err, "Profile"),
  })
  const effectiveRole = user.role || user.primary_role || "Authenticated"
  const assignedRoles = Array.isArray(user.roles) && user.roles.length
    ? user.roles
    : (user.role || user.primary_role ? [user.role || user.primary_role] : [])
  const authTypes = Array.isArray(user.auth_type) ? user.auth_type : (user.auth_type ? [user.auth_type] : [])
  const canChangePassword = authTypes.includes("local")
  const permissions = Array.isArray(user.permissions) ? user.permissions : []
  const environments = Array.isArray(user.environments) ? user.environments : []
  const assays = Array.isArray(user.asp_ids) ? user.asp_ids : []
  const assayGroups = Array.isArray(user.asp_groups) ? user.asp_groups : []

  return (
    <PageShell
      eyebrow="Account"
      title="Profile"
      description="View your active session and manage your local account password."
    >
      {isLoading ? (
        <AppLoader label="Loading profile" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load profile"}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_28rem]">
          <section className="glass-card p-4">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-xl bg-primary/10 p-3 text-primary">
                <User className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold">{data?.user?.fullname || data?.user?.username || "Current user"}</h2>
                <p className="text-sm text-muted-foreground">{data?.user?.job_title || effectiveRole}</p>
              </div>
            </div>
            <dl className="grid gap-3 rounded-lg border border-border bg-muted/20 p-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Username</dt>
                <dd className="mt-1 font-semibold">{data?.user?.username || data?.user?._id || "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Email</dt>
                <dd className="mt-1 font-semibold">
                  {data?.user?.email ? (
                    <a className="link-text inline-flex items-center gap-1" href={`mailto:${data.user.email}`}>
                      <Mail className="h-3.5 w-3.5" />
                      {data.user.email}
                    </a>
                  ) : "-"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Name</dt>
                <dd className="mt-1 font-semibold">{data?.user?.firstname || data?.user?.lastname ? `${data?.user?.firstname || ""} ${data?.user?.lastname || ""}`.trim() : "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Highest role</dt>
                <dd className="mt-1"><RoleChip role={effectiveRole} /></dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Access level</dt>
                <dd className="mt-1 font-semibold">{data?.user?.access_level ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Authentication</dt>
                <dd className="mt-2 flex flex-wrap gap-1">
                  {authTypes.length ? authTypes.map((auth: string) => <AuthChip key={auth} value={auth} />) : "-"}
                </dd>
              </div>
              <div className="sm:col-span-2 xl:col-span-3">
                <dt className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Assigned roles</dt>
                <dd className="mt-2 flex flex-wrap gap-2">
                  {assignedRoles.length ? assignedRoles.map((role: string) => (
                    <label
                      key={role}
                      className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1 text-xs font-semibold"
                    >
                      <input type="checkbox" checked readOnly className="h-3.5 w-3.5 accent-primary" />
                      <RoleChip role={role} />
                    </label>
                  )) : (
                    <span className="text-sm text-muted-foreground">No roles assigned</span>
                  )}
                </dd>
              </div>
            </dl>
            <section className="mt-4 rounded-lg border border-border bg-background/70 p-3">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Editable profile</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {([
                  ["firstname", "First name"],
                  ["lastname", "Last name"],
                  ["fullname", "Display name"],
                  ["job_title", "Job title"],
                ] as const).map(([field, label]) => <label key={field} className="block text-sm font-semibold">{label}<input className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" value={profileDraft[field]} onChange={(event) => setProfileDraft((current) => ({ ...current, [field]: event.target.value }))} /></label>)}
              </div>
              <button type="button" onClick={() => updateProfile.mutate()} disabled={updateProfile.isPending} className="mt-3 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50">Save profile</button>
              <p className="mt-2 text-xs text-muted-foreground">Roles, assay scope, authentication providers, account status, email, username, and passwords are managed through their dedicated administrative or security workflows.</p>
            </section>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <ScopeCard title="Profiles" icon={BadgeCheck} values={environments} empty="No profile scope" />
              <ScopeCard title="Assays" icon={Dna} values={assays} empty="No assay scope" />
              <ScopeCard title="Assay groups" icon={ShieldCheck} values={assayGroups} empty="No assay group scope" />
            </div>
            <section className="mt-4 rounded-lg border border-border bg-background/70 p-3">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Effective permissions</h3>
              {permissions.length ? (
                <div className="flex max-h-48 flex-wrap gap-1.5 overflow-auto pr-1">
                  {permissions.map((permission: string) => (
                    <span key={permission} className="rounded-md border border-border bg-muted/40 px-2 py-1 text-[11px] font-semibold text-muted-foreground" title={permission}>
                      {permission.split(":").slice(0, 2).join(":")}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Permissions are inherited from assigned roles.</p>
              )}
            </section>
          </section>

          <section className="glass-card p-4">
            <div className="mb-4 flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">Change Password</h2>
            </div>
            <div className="space-y-3">
              {!canChangePassword && (
                <div className="rounded-lg border border-warn/35 bg-warn/10 p-3 text-xs font-semibold text-warn">
                  This account is not configured for local password changes. LDAP-only accounts are managed by the center identity provider.
                </div>
              )}
              <label className="block text-sm font-semibold">
                Current password
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  disabled={!canChangePassword}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm font-semibold">
                New password
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  disabled={!canChangePassword}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
              <button
                onClick={() => changePassword.mutate()}
                disabled={!canChangePassword || !currentPassword || !newPassword || changePassword.isPending}
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

function RoleChip({ role }: { role: string }) {
  return <span className="rounded-full border border-primary/25 bg-primary/10 px-2 py-0.5 text-[11px] font-black uppercase text-primary">{role}</span>
}

function AuthChip({ value }: { value: string }) {
  const isLocal = value === "local"
  return (
    <span className={isLocal ? "rounded-full border border-tier3/30 bg-tier3/10 px-2 py-0.5 text-[11px] font-black uppercase text-tier3" : "rounded-full border border-pass/30 bg-pass/10 px-2 py-0.5 text-[11px] font-black uppercase text-pass"}>
      {value}
    </span>
  )
}

function ScopeCard({ title, icon: Icon, values, empty }: { title: string; icon: any; values: string[]; empty: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {values.length ? values.map((value) => (
          <span key={value} className="rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[11px] font-bold uppercase text-muted-foreground">
            {value}
          </span>
        )) : <span className="text-xs text-muted-foreground">{empty}</span>}
      </div>
    </div>
  )
}
