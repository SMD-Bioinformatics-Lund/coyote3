import { Component, type ErrorInfo, type ReactNode } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"

type Props = { children: ReactNode }
type State = { error: Error | null }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Uncaught UI error", error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-6">
        <section className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-sm">
          <AlertTriangle className="mb-4 h-8 w-8 text-destructive" aria-hidden="true" />
          <h1 className="text-xl font-bold text-foreground">This view could not be displayed</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            The application encountered an unexpected interface error. Reload the page to restore
            the current view.
          </p>
          <Button className="mt-5" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4" />
            Reload page
          </Button>
        </section>
      </main>
    )
  }
}
