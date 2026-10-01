import { PageShell } from "@/components/layout/PageShell"
import { Home } from "lucide-react"
import { Link } from "react-router-dom"


export function NotFoundPage() {
  return (
    <PageShell eyebrow="404" title="Page not found" description="The requested Coyote3 view does not exist in this UI.">
      <section className="surface-panel p-5">
        <p className="text-sm text-muted-foreground">Check the URL or return to the sample dashboard.</p>
        <Link to="/" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground">
          <Home className="h-4 w-4" />
          Home
        </Link>
      </section>
    </PageShell>
  )
}
