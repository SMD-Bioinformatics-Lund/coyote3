import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Eye, EyeOff, Loader2, Sun, Cloud } from "lucide-react"
import { useTheme } from "next-themes"
import { apiPath, appPath } from "@/lib/runtime-paths"

export function Login() {
  const navigate = useNavigate()
  const [provider, setProvider] = useState<"local" | "ldap">("local")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { theme } = useTheme()
  const isDark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch(apiPath("/auth/sessions"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.error || data.detail || "Sign in failed")
        return
      }

      navigate("/")
    } catch (err: any) {
      setError(err.message || "Sign in failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page relative">
      {/* Background Scenery Elements */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden flex flex-col justify-between">

        {/* Top Section: Sun/Moon & Clouds */}
        <div className="relative w-full h-1/2">
          {/* Sun / Moon top right */}
          <div className="absolute top-12 right-[15%] opacity-40">
            {isDark ? (
              <div
                className="w-[180px] h-[180px] rounded-full bg-slate-50"
                style={{
                  boxShadow: "0 0 60px 15px rgba(253, 253, 253, 1), inset -20px -20px 40px rgba(199, 199, 199, 1)",
                  background: "radial-gradient(circle at 50% 60%, #ffffffec, #fffffff1)"
                }}
              />
            ) : (
              <Sun size={200} strokeWidth={0.5} className="text-amber-500" />
            )}
          </div>

          {/* Clouds */}
          <div className={`absolute top-24 left-[20%] opacity-30 ${isDark ? 'text-indigo-200' : 'text-sky-500'}`}>
            <Cloud size={140} strokeWidth={0.5} />
          </div>
          <div className={`absolute top-48 right-[35%] opacity-30 ${isDark ? 'text-indigo-200' : 'text-sky-400'}`}>
            <Cloud size={100} strokeWidth={0.5} />
          </div>
        </div>

        {/* Bottom Section: Logo howling at moon */}
        <div className="relative w-full h-1/2">
          {/* Big Coyote Logo bottom left */}
          <div className="absolute -bottom-16 -left-16 opacity-[0.04]">
            <img
              src={appPath("/logo.png")}
              alt=""
              className="w-[900px] h-[650px] dark:invert"
            />
          </div>
        </div>
      </div>

      <header className="login-header relative z-10">
        <div className="inline-flex min-w-max items-center gap-2.5">
          <img
            src={appPath("/logo.png")}
            alt="Coyote3"
            className="w-10 h-8 dark:invert"
          />
          <span className="text-3xl tracking-[-0.035em] font-bold">COYOT3</span>
        </div>
        <ThemeToggle />
      </header>

      <section className="login-layout">
        <div className="login-intro">
          <h1 className="login-title">
            Genomic variant analysis,<br /> from sequence to report.
          </h1>
          <p className="login-description">
            A focused clinical workspace for processing, interpretation,
            and traceable reporting of complex genomic data.
          </p>
        </div>

        <section className="login-card">
          <h2 className="text-2xl font-[750]">Welcome back</h2>
          <p className="text-muted-foreground mt-1.5 mb-6 text-sm">
            Sign in to continue to Coyote3.
          </p>

          <div className="grid grid-cols-2 p-1 bg-muted rounded-lg mb-6 border border-border">
            <button
              type="button"
              onClick={() => setProvider("local")}
              className={`py-1.5 text-sm font-medium rounded-md transition-colors duration-100 ${
                provider === "local"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Local Account
            </button>
            <button
              type="button"
              onClick={() => setProvider("ldap")}
              className={`py-1.5 text-sm font-medium rounded-md transition-colors duration-100 ${
                provider === "ldap"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              LDAP Login
            </button>
          </div>

          {error && (
            <div className="p-3 text-sm rounded-md bg-destructive/15 text-destructive border border-destructive/20 mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">
                {provider === "ldap" ? "Email" : "Username"}
              </Label>
              <Input
                id="username"
                type={provider === "ldap" ? "email" : "text"}
                placeholder={provider === "ldap" ? "name@domain.com" : ""}
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
                disabled={loading}
                className="h-11"
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="password">Password</Label>
                <Link to="/forgot-password" className="text-xs font-semibold text-primary hover:underline">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  className="h-11 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-11 text-base mt-2"
              disabled={loading || !username || !password}
            >
              {loading ? (
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              ) : null}
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <p className="text-sm text-muted-foreground mt-5">
            {provider === "ldap"
              ? "Use your organization credentials. Your Coyote3 access comes from your local user profile."
              : "Use your existing Coyote3 local account."}
          </p>
          <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3 text-sm">
            <p className="font-semibold text-foreground">Public resources</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Assay catalog, gene lists, and public reference views are available without signing in.
            </p>
            <Link
              to="/public"
              className="mt-3 inline-flex items-center rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-muted"
            >
              Open public catalog
            </Link>
          </div>
        </section>
      </section>

      <footer className="login-footer">
        <span>Coyote3 v4.0.0</span>
        <span className="font-extrabold tracking-[0.08em] text-primary uppercase">DEVELOPMENT</span>
        <span>Section for Molecular Diagnostics</span>
      </footer>
    </main>
  )
}
