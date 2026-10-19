"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider, useTheme } from "next-themes"
import { scheduledTheme } from "@/lib/theme-schedule"

function ThemeSchedule({ onResolve }: { onResolve: (theme: "light" | "dark" | undefined) => void }) {
  const { theme } = useTheme()
  React.useLayoutEffect(() => {
    if (theme !== "auto") { onResolve(undefined); return }
    const refresh = () => onResolve(scheduledTheme())
    refresh()
    const timer = window.setInterval(refresh, 30_000)
    window.addEventListener("focus", refresh)
    document.addEventListener("visibilitychange", refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("focus", refresh)
      document.removeEventListener("visibilitychange", refresh)
    }
  }, [theme, onResolve])
  return null
}

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  const [scheduled, setScheduled] = React.useState<"light" | "dark">()
  return <NextThemesProvider themes={["light", "dark", "auto"]} disableTransitionOnChange
    {...props} forcedTheme={props.forcedTheme || scheduled}>
    <ThemeSchedule onResolve={setScheduled} />
    {children}
  </NextThemesProvider>
}
