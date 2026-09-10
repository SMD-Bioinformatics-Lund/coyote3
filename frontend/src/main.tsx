import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from "@/components/layout/theme-provider"
import { NotificationProvider } from "@/components/notifications/NotificationProvider"
import { GlobalRichTooltip } from "@/components/ui/global-rich-tooltip"
import { AppErrorBoundary } from "@/components/errors/AppErrorBoundary"
import App from './App.tsx'
import './index.css'
import { reportUiError } from "@/lib/api"

window.addEventListener("error", (event) => reportUiError(event.error || event.message))
window.addEventListener("unhandledrejection", (event) => reportUiError(event.reason))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme" attribute="class">
        <NotificationProvider>
          <App />
          <GlobalRichTooltip />
        </NotificationProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  </StrictMode>,
)
