"use client"

import { Moon, Sun, SunMoon } from "lucide-react"
import { useTheme } from "next-themes"

import { cn } from "@/lib/utils"

export function ThemeToggle({ className, value, onChange, disabled = false }: {
  className?: string
  value?: "auto" | "light" | "dark"
  onChange?: (theme: "auto" | "light" | "dark") => void
  disabled?: boolean
}) {
  const { theme, setTheme } = useTheme()
  const current = value || (theme === "light" || theme === "dark" ? theme : "auto")
  const next = current === "auto" ? "light" : current === "light" ? "dark" : "auto"
  const Icon = current === "auto" ? SunMoon : current === "light" ? Sun : Moon
  const label = `Theme: ${current}. Switch to ${next}`

  return (
    <button type="button" aria-label={label} title={label} disabled={disabled}
      onClick={() => onChange ? onChange(next) : setTheme(next)}
      className={cn("inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-transparent bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50", className)}>
      <Icon aria-hidden="true" className="h-5 w-5" />
    </button>
  )
}
