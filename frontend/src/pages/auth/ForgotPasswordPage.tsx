import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { ArrowLeft, Loader2 } from "lucide-react"
import { FormEvent, useState } from "react"
import { Link } from "react-router-dom"
import { AuthShell } from "./PasswordAuthShell"

export function ForgotPassword() {
  const [username, setUsername] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage("")
    setError("")
    setLoading(true)
    try {
      await api.post("/auth/password/reset/request", { username })
      setMessage("If this account can reset its password, a reset email has been sent.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request password reset.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Reset local access"
      description="Request a password reset token for a local Coyote3 account."
    >
      <h2 className="text-2xl font-bold">Forgot password</h2>
      <p className="mb-6 mt-1.5 text-sm text-muted-foreground">
        Enter the username or email registered for your local account.
      </p>
      {message && <div className="mb-4 rounded-md border border-pass/30 bg-pass/10 p-3 text-sm text-pass">{message}</div>}
      {error && <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="username">Username or email</Label>
          <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} required disabled={loading} />
        </div>
        <Button type="submit" className="h-11 w-full" disabled={loading || !username}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Request reset
        </Button>
      </form>
      <Link to="/login" className="link-text mt-5 inline-flex items-center gap-2 text-sm font-semibold">
        <ArrowLeft className="h-4 w-4" />
        Back to sign in
      </Link>
    </AuthShell>
  )
}
