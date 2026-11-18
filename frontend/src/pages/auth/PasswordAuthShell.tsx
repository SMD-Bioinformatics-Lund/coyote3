// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { BrandLogo } from "@/components/layout/BrandLogo"
import { AppFooter } from "@/components/layout/AppFooter"
import { ThemeToggle } from "@/components/layout/theme-toggle"
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
    <div className="flex h-dvh flex-col overflow-hidden">
      <main className="login-page relative">
        <header className="login-header relative z-10">
          <Link to="/login" aria-label="Back to sign in" className="inline-flex min-w-max items-center gap-2.5">
            <BrandLogo />
          </Link>
          <ThemeToggle />
        </header>

        <div className="login-scroll-viewport app-scroll-viewport">
          <section className="login-layout">
            <div className="login-intro">
              <h1 className="login-title">{title}</h1>
              <p className="login-description">{description}</p>
            </div>
            <section className="login-card">{children}</section>
          </section>
        </div>
      </main>
      <AppFooter />
    </div>
  )
}
