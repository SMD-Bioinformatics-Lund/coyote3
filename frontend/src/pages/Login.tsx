import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Eye, EyeOff, Loader2, Cloud } from "lucide-react"
import { useTheme } from "next-themes"
import { apiPath, appPath } from "@/lib/runtime-paths"
import { runtimeConfig } from "@/lib/runtime-config"

export function Login() {
  const navigate = useNavigate()
  const [providers, setProviders] = useState<string[]>([])
  const [provider, setProvider] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"
  const { appVersion, organizationName } = runtimeConfig

  useEffect(() => {
    let active = true
    fetch(apiPath("/auth/providers"))
      .then(async response => {
        if (!response.ok) throw new Error("Login providers are unavailable")
        return response.json() as Promise<{ providers?: string[] }>
      })
      .then(data => {
        const enabled = (data.providers || []).filter(value => value === "local" || value === "ldap")
        if (!active) return
        setProviders(enabled)
        setProvider(enabled[0] || "")
      })
      .catch(error => {
        if (active) setError(error instanceof Error ? error.message : "Login providers are unavailable")
      })
    return () => { active = false }
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch(apiPath("/auth/sessions"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, provider })
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
          {isDark ? (
            <div className="login-stars" aria-hidden="true" />
          ) : (
            <div className="login-birds" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
          )}

          {/* Sun / Moon top right */}
          <div className={`absolute top-12 right-[15%] ${isDark ? "opacity-75" : "opacity-50"}`}>
            {isDark ? (
              <div className="login-moon" aria-hidden="true" />
            ) : (
              <div className="login-sun" aria-hidden="true" />
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

        {/* Bottom Section: theme-specific pencil sketch */}
        <div className="relative w-full h-1/2">
          <div className="absolute bottom-[-2rem] -left-12 w-[min(130vw,1400px)] opacity-[0.2] dark:-bottom-15 dark:left-0 dark:w-[min(130vw,1400px)] dark:opacity-[0.26]">
            <img
              src={appPath(isDark ? "/coyote-howling-sketch.svg" : "/coyote-walking-sketch.svg")}
              alt=""
              className="h-auto w-full"
            />
          </div>
        </div>
      </div>

      <header className="login-header relative z-10">
        <div className="inline-flex min-w-max items-center gap-2.5">
          <img
            src={appPath("/logo.png")}
            alt={organizationName}
            className="w-10 h-8 dark:invert"
          />
          <span className="text-3xl tracking-wider font-bold">COYOT3</span>
        </div>
        <ThemeToggle />
      </header>

      <section className="login-layout">
        <div className="login-intro">
          <h1 className="login-title">
            From genomic data to confident clinical insight.
          </h1>
          <p className="login-description">
            Coyote3 brings variant analysis, interpretation, and traceable reporting
            together in one focused clinical genomics workspace.
          </p>
        </div>

        <section className="login-card">
          <h2 className="text-2xl font-[750]">Welcome back</h2>
          <p className="text-muted-foreground mt-1 mb-4 text-sm">
            Sign in to continue.
          </p>

          {providers.length > 1 ? (
            <div className="grid grid-cols-2 p-1 bg-muted rounded-lg mb-6 border border-border">
              {providers.map(enabledProvider => (
                <button
                  key={enabledProvider}
                  type="button"
                  onClick={() => setProvider(enabledProvider)}
                  className={`py-1.5 text-sm font-medium rounded-md transition-colors duration-100 ${
                    provider === enabledProvider
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {enabledProvider === "ldap" ? "LDAP Login" : "Local Account"}
                </button>
              ))}
            </div>
          ) : <div className="mb-6" />}

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
              disabled={loading || !provider || !username || !password}
            >
              {loading ? (
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              ) : null}
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <p className="text-sm text-muted-foreground mt-5">
            {provider === "ldap"
              ? `Use your organization credentials. Your access comes from your local user profile.`
              : `Use your existing local account.`}
          </p>
          <div className="mt-2 rounded-lg border border-border bg-muted/40 p-3 text-sm">
            <p className="font-semibold text-foreground">Public resources</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Assay catalog, gene lists, and public reference views are available without signing in.
            </p>
            <Link
              to="/public"
              className="mt-2 inline-flex items-center rounded-lg border border-border bg-background px-3 py-1 text-xs font-bold text-primary transition-colors hover:bg-muted"
            >
              Open public catalog
            </Link>
          </div>
        </section>
      </section>

      <footer className="login-footer">
        <span>Coyote3 {appVersion}</span>
        <span className="font-extrabold tracking-[0.08em] text-primary uppercase">DEVELOPMENT</span>
        <span className="login-organization-name">{organizationName}</span>
      </footer>
    </main>
  )
}
