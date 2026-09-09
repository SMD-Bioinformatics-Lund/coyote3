import { useEffect, useState, type FormEvent } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { KeyRound, LogOut } from "lucide-react"
import { api } from "@/lib/api"
import { appPath } from "@/lib/runtime-paths"
import { clearSessionState } from "@/lib/session-state"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { EnvironmentBanner } from "@/components/layout/EnvironmentBanner"

export function ChangePassword() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  const identity = useQuery({
    queryKey: ["password-change-identity"],
    retry: false,
    queryFn: () => api.get<{ username: string }>("/auth/whoami").then((response) => response.data),
  })
  useEffect(() => {
    if (identity.isError) navigate("/login", { replace: true })
  }, [identity.isError, navigate])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password !== confirmation) {
      setError("New password and confirmation must match.")
      return
    }
    if (password === current) {
      setError("Choose a different password.")
      return
    }
    setPending(true)
    setError("")
    try {
      await api.post("/auth/password/change", {
        current_password: current,
        new_password: password,
        confirm_password: confirmation,
      })
      setCurrent("")
      setPassword("")
      setConfirmation("")
      await clearSessionState(client)
      navigate("/login?password=changed", { replace: true })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to change password.")
    } finally {
      setPending(false)
    }
  }
  const signOut = async () => {
    try {
      await api.delete("/auth/sessions/current")
      await clearSessionState(client)
      navigate("/login", { replace: true })
    } catch {
      setError("Unable to sign out. Please try again.")
    }
  }
  return <div className="min-h-screen bg-background">
    <EnvironmentBanner />
    <main className="mx-auto w-full max-w-lg space-y-6 px-4 py-10">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <img src={appPath("/logo.png")} alt="Coyote3" className="h-10 w-16 object-contain dark:invert" />
          <span className="text-xl font-semibold">Coyote3</span>
        </div>
        <Button variant="ghost" onClick={signOut} disabled={pending}>
          <LogOut className="h-4 w-4" />Sign out
        </Button>
      </header>
      <h1 className="type-page-title">Change your password</h1>
      <p className="text-sm text-muted-foreground">Set a personal password before continuing. You will sign in again with your new password.</p>
      <p className="text-sm text-muted-foreground">Use at least 10 characters with uppercase and lowercase letters, a number, and a symbol.</p>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="temporary-password">Current password</Label>
          <Input id="temporary-password" type="password" autoComplete="current-password"
            required value={current} onChange={(event) => setCurrent(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="new-password">New password</Label>
          <Input id="new-password" type="password" autoComplete="new-password" minLength={10}
            required value={password} onChange={(event) => setPassword(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm-password">Confirm new password</Label>
          <Input id="confirm-password" type="password" autoComplete="new-password"
            required value={confirmation} aria-invalid={!!confirmation && password !== confirmation}
            onChange={(event) => setConfirmation(event.target.value)} />
        </div>
        {confirmation && password !== confirmation && <p className="text-sm text-destructive">Passwords do not match.</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={!identity.data || pending || !current || !password || password !== confirmation || password === current}>
          <KeyRound className="h-4 w-4" />{pending ? "Changing password..." : "Change password"}
        </Button>
      </form>
    </main>
  </div>
}
