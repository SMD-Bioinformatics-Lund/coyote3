// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Notice } from "@/components/ui/notice"
import { LoadingIndicator } from "@/components/ui/loading-indicator"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { icon } from "@/lib/assets"
import { FormEvent, useState } from "react"
import { Link } from "react-router-dom"
import { AuthShell } from "./PasswordAuthShell"

export function ForgotPassword() {
  const [username, setUsername] = useState("")
  const [provider, setProvider] = useState("auto")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage("")
    setError("")
    setLoading(true)
    try {
      await api.post("/auth/password/reset/request", { username, provider })
      setMessage("If the account is eligible, recovery instructions will be sent to its saved email or a request will be sent to administrators.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request password reset.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Recover account access"
      description="Request help with your local or LDAP account."
    >
      <h2 className="text-2xl font-bold">Forgot password</h2>
      <p className="mb-6 mt-1.5 text-sm text-muted-foreground">
        Enter your username. Local accounts receive a reset link at their saved email address. LDAP resets are handled by administrators through the external directory service.
      </p>
      {message && <Notice tone="success" className="mb-4">{message}</Notice>}
      {error && <Notice tone="danger" className="mb-4">{error}</Notice>}
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="username">Username</Label>
          <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} required disabled={loading} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="recovery-provider">Account type</Label>
          <select id="recovery-provider" value={provider} onChange={event => setProvider(event.target.value)} disabled={loading}
            className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/40">
            <option value="auto">Automatic (local first)</option>
            <option value="local">Local</option>
            <option value="ldap">LDAP</option>
          </select>
          <p className="text-xs text-muted-foreground">If you use both sign-in methods, select the one you need to recover. Without a saved email, local recovery also requires administrator assistance.</p>
        </div>
        <Button type="submit" className="h-11 w-full" disabled={loading || !username}>
          {loading && <LoadingIndicator className="mr-2 h-4 w-4" />}
          Request reset
        </Button>
      </form>
      <Link to="/login" className="link-text mt-5 inline-flex items-center gap-2 text-sm font-semibold">
        <icon.arrowLeft className="h-4 w-4" />
        Back to sign in
      </Link>
    </AuthShell>
  )
}
