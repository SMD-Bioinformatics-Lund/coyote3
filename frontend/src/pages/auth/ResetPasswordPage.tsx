import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { ArrowLeft, Loader2 } from "lucide-react"
import { FormEvent, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { AuthShell } from "./PasswordAuthShell"

export function ResetPassword() {
  const [params] = useSearchParams()
  const [token, setToken] = useState(params.get("token") || "")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage("")
    setError("")
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.")
      return
    }
    setLoading(true)
    try {
      await api.post("/auth/password/reset/confirm", { token, new_password: newPassword })
      setMessage("Password updated. You can sign in with the new password.")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Set a new password"
      description="Complete the local account password reset flow with the reset token."
    >
      <h2 className="text-2xl font-bold">Reset password</h2>
      <p className="mb-6 mt-1.5 text-sm text-muted-foreground">
        Paste the token from the reset link if it was not included in the URL.
      </p>
      {message && <div className="mb-4 rounded-md border border-pass/30 bg-pass/10 p-3 text-sm text-pass">{message}</div>}
      {error && <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="token">Reset token</Label>
          <Input id="token" value={token} onChange={(event) => setToken(event.target.value)} required disabled={loading} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="new-password">New password</Label>
          <Input id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required disabled={loading} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <Input id="confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required disabled={loading} />
        </div>
        <Button type="submit" className="h-11 w-full" disabled={loading || !token || !newPassword || !confirmPassword}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save password
        </Button>
      </form>
      <Link to="/login" className="link-text mt-5 inline-flex items-center gap-2 text-sm font-semibold">
        <ArrowLeft className="h-4 w-4" />
        Back to sign in
      </Link>
    </AuthShell>
  )
}
