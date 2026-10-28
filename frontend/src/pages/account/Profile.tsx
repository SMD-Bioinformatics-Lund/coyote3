import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { icon as appIcon } from "@/lib/assets"
import { api } from "@/lib/api"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { UserUiSettingsControls } from "@/components/users/UserUiSettingsControls"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useUpdateUiSettings } from "@/lib/user-settings"
import "@/styles/account-profile.css"

export function Profile() {
  const queryClient = useQueryClient()
  const updateUiSettings = useUpdateUiSettings()
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
      description="View your active session and manage your profile, interface settings, and local password."
    >
      {isLoading ? (
        <AppLoader label="Loading profile" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load profile"}
        </div>
      ) : (
        <div className="account-profile grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <section className="min-w-0">
            <section aria-label="Account details" className="account-card account-identity overflow-hidden rounded-2xl">
              <div className="flex items-start gap-3 p-4 sm:p-5">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <appIcon.user className="h-6 w-6" aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="type-card-title break-words text-foreground">
                    {user.fullname || [user.firstname, user.lastname].filter(Boolean).join(" ") || user.username || "Current user"}
                  </h2>
                  {user.job_title && <p className="mt-1 type-body-sm text-muted-foreground">{user.job_title}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 type-body-sm">
                    <span className="break-all text-muted-foreground">
                      <span className="sr-only">Username: </span>@{user.username || user._id || "-"}
                    </span>
                    {user.email && (
                      <a className="link-text inline-flex min-w-0 items-center gap-1.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`mailto:${user.email}`}>
                        <appIcon.mail className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        <span className="break-all">{user.email}</span>
                      </a>
                    )}
                  </div>
                </div>
              </div>
              <dl className="grid border-t border-border/40 sm:grid-cols-3">
                <div className="p-4 sm:p-5">
                  <dt className="type-label text-muted-foreground">Highest role</dt>
                  <dd className="mt-2"><RoleChip role={effectiveRole} /></dd>
                </div>
                <div className="p-4 sm:p-5">
                  <dt className="type-label text-muted-foreground">Authentication</dt>
                  <dd className="mt-2 flex flex-wrap gap-1.5">
                    {authTypes.length ? authTypes.map((auth: string) => <AuthChip key={auth} value={auth} />) : <span className="type-body-sm text-muted-foreground">Not specified</span>}
                  </dd>
                </div>
                <div className="p-4 sm:p-5">
                  <dt className="type-label text-muted-foreground">Access level</dt>
                  <dd className="mt-2 type-body-sm font-medium tabular-nums text-foreground">{user.access_level ?? "-"}</dd>
                </div>
                <div className="px-4 pb-5 sm:col-span-3 sm:px-5">
                  <dt className="type-label text-muted-foreground">Assigned roles</dt>
                  <dd className="mt-2 flex flex-wrap gap-2">
                    {assignedRoles.length ? assignedRoles.map((role: string) => (
                      <RoleChip key={role} role={role} />
                    )) : <span className="type-body-sm text-muted-foreground">No roles assigned</span>}
                  </dd>
                </div>
              </dl>
            </section>
            <section className="account-card mt-6 rounded-2xl p-5 sm:p-6">
              <h3 className="mb-4 type-card-title text-foreground">Personal details</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {([
                  ["firstname", "First name"],
                  ["lastname", "Last name"],
                  ["fullname", "Display name"],
                  ["job_title", "Job title"],
                ] as const).map(([field, label]) => <div key={field}><label className="block text-sm font-semibold">{label}<input aria-describedby={field === "fullname" ? "profile-display-name-help" : undefined} className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" value={profileDraft[field]} onChange={(event) => setProfileDraft((current) => ({ ...current, [field]: event.target.value }))} /></label>{field === "fullname" && <p id="profile-display-name-help" className="mt-1 type-meta text-muted-foreground">Full name shown in your profile and account menus. Your username remains your login identifier.</p>}</div>)}
              </div>
              <button type="button" onClick={() => updateProfile.mutate()} disabled={updateProfile.isPending} className="mt-3 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50">Save profile</button>
              <p className="mt-2 text-xs text-muted-foreground">Roles, assay scope, authentication providers, account status, email, username, and passwords are managed through their dedicated administrative or security workflows.</p>
            </section>
            <section className="account-card mt-6 rounded-2xl p-5 sm:p-6">
              <div className="mb-3">
                <h3 className="type-card-title text-foreground">Preferences</h3>
                <p className="mt-1 text-xs text-muted-foreground">Layout choices are saved to your account and restored on future sessions.</p>
              </div>
              <UserUiSettingsControls
                value={user.ui_settings}
                disabled={updateUiSettings.isPending}
                onChange={(settings) => updateUiSettings.mutate(settings)}
              />
            </section>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <ScopeCard title="Profiles" icon={appIcon.badgeCheck} values={environments} empty="No profile scope" />
              <ScopeCard title="Assays" icon={appIcon.dna} values={assays} empty="No assay scope" />
              <ScopeCard title="Assay groups" icon={appIcon.shieldCheck} values={assayGroups} empty="No assay group scope" />
            </div>
            <section className="account-card mt-6 rounded-2xl p-5 sm:p-6">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Effective permissions</h3>
              {permissions.length ? (
                <div className="flex max-h-48 flex-wrap gap-1.5 overflow-auto pr-1">
                  {permissions.map((permission: string) => (
                    <span key={permission} className="rounded-md border border-border bg-muted/40 px-2 py-1 type-meta font-semibold text-muted-foreground" title={permission}>
                      {permission.split(":").slice(0, 2).join(":")}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Permissions are inherited from assigned roles.</p>
              )}
            </section>
          </section>

          <section className="account-card rounded-2xl p-5 sm:p-6">
            <div className="mb-4 flex items-center gap-2">
              <appIcon.keyRound className="h-5 w-5 text-primary" />
              <h2 className="type-card-title">Password & security</h2>
            </div>
            <div className="space-y-3">
              {user.must_change_password && (
                <p role="status" className="text-sm font-semibold text-warn">Change your temporary password before accessing clinical data.</p>
              )}
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
                {changePassword.isPending && <appIcon.activity className="h-4 w-4 animate-spin" />}
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
  return <span className="inline-flex items-center rounded-md border border-primary/25 bg-primary/10 px-2 py-1 type-meta font-medium text-primary">{role}</span>
}

function AuthChip({ value }: { value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1 type-meta font-medium text-foreground">
      <appIcon.keyRound className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
      {value === "local" ? "Local account" : value.toUpperCase()}
    </span>
  )
}

function ScopeCard({ title, icon: Icon, values, empty }: { title: string; icon: any; values: string[]; empty: string }) {
  return (
    <div className="account-card rounded-xl p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {values.length ? values.map((value) => (
          <span key={value} className="rounded-md border border-border bg-muted/40 px-2 py-0.5 type-meta font-bold uppercase text-muted-foreground">
            {value}
          </span>
        )) : <span className="text-xs text-muted-foreground">{empty}</span>}
      </div>
    </div>
  )
}
