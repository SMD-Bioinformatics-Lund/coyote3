import { BrandWordmark } from "@/components/layout/BrandWordmark"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { appPath } from "@/lib/runtime-paths"
import { ReactNode } from "react"
import { Link } from "react-router-dom"


export function AuthShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <main className="login-page relative">
      <header className="login-header relative z-10">
        <Link to="/login" className="inline-flex min-w-max items-center gap-2.5">
          <img src={appPath("/logo.png")} alt="Coyote3" className="h-8 w-10 dark:invert" />
          <BrandWordmark />
        </Link>
        <ThemeToggle />
      </header>

      <section className="login-layout">
        <div className="login-intro">
          <h1 className="login-title">{title}</h1>
          <p className="login-description">{description}</p>
        </div>
        <section className="login-card">{children}</section>
      </section>

      <footer className="login-footer">
        <span>Coyote3 v4.0.0</span>
        <span className="font-semibold tracking-[0.08em] text-primary uppercase">DEVELOPMENT</span>
        <span>Section for Molecular Diagnostics</span>
      </footer>
    </main>
  )
}
