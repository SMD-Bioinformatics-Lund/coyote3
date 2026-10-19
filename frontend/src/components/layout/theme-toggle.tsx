"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { cn } from "@/lib/utils"

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()

  return (
    <label className={cn("inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-foreground", className)}>
      <Sun aria-hidden="true" className="h-4 w-4 shrink-0 dark:hidden" />
      <Moon aria-hidden="true" className="hidden h-4 w-4 shrink-0 dark:block" />
      <span className="sr-only">Theme</span>
      <select value={theme || "auto"} onChange={(event) => setTheme(event.target.value)}
        className="min-w-0 rounded bg-card py-1 type-body-sm text-foreground focus-visible:outline-ring"
        title="Automatic: light 07:00–19:00, dark otherwise (device local time)">
        <option value="auto">Automatic</option>
        <option value="system">Device preference</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  )
}
