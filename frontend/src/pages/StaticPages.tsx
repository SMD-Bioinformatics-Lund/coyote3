import { Link } from "react-router-dom"
import { FileText, Home, Mail, ShieldCheck } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"

const docs = {
  about: {
    eyebrow: "Docs",
    title: "About Coyote3",
    icon: FileText,
    body: [
      "Coyote3 is a clinical genomics interpretation workspace for sample review, variant classification, and traceable report generation.",
      "This React page restores the historical About route in the migrated UI. The authoritative operational and user documentation remains in the repository documentation tree.",
    ],
  },
  changelog: {
    eyebrow: "Docs",
    title: "Changelog",
    icon: FileText,
    body: [
      "The React UI exposes the Coyote3 changelog for release review.",
      "Release notes should be populated from the project changelog source once the documentation API is connected.",
    ],
  },
  license: {
    eyebrow: "Docs",
    title: "License",
    icon: ShieldCheck,
    body: [
      "This route restores the historical license page surface.",
      "Keep deployment-specific license text and third-party notices synchronized with the maintained project documentation.",
    ],
  },
}

export function StaticDocPage({ kind }: { kind: keyof typeof docs }) {
  const doc = docs[kind]
  const Icon = doc.icon
  return (
    <PageShell eyebrow={doc.eyebrow} title={doc.title} description="Migrated historical documentation surface.">
      <section className="surface-panel border-t-4 border-t-panel p-5">
        <div className="mb-4 flex items-center gap-3">
          <div className="rounded-lg bg-panel/10 p-2 text-panel"><Icon className="h-5 w-5" /></div>
          <h2 className="text-lg font-bold">{doc.title}</h2>
        </div>
        <div className="space-y-3 text-sm leading-6 text-muted-foreground">
          {doc.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        </div>
      </section>
    </PageShell>
  )
}

export function ContactPage() {
  return (
    <PageShell eyebrow="Public" title="Contact" description="Historical public contact surface for assay and platform support.">
      <section className="surface-panel border-t-4 border-t-dna p-5">
        <div className="mb-4 flex items-center gap-3">
          <div className="rounded-lg bg-dna/10 p-2 text-dna"><Mail className="h-5 w-5" /></div>
          <h2 className="text-lg font-bold">Contact and Support</h2>
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          Contact details are deployment-specific. Configure the backend public contact payload to show center contacts, assay support, and operational escalation details here.
        </p>
        <Link to="/catalog" className="mt-4 inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
          <Home className="h-4 w-4" />
          Back to catalog
        </Link>
      </section>
    </PageShell>
  )
}

export function NotFoundPage() {
  return (
    <PageShell eyebrow="404" title="Page not found" description="The requested Coyote3 view does not exist in this UI.">
      <section className="surface-panel border-t-4 border-t-warn p-5">
        <p className="text-sm text-muted-foreground">Check the URL or return to the sample dashboard.</p>
        <Link to="/" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground">
          <Home className="h-4 w-4" />
          Home
        </Link>
      </section>
    </PageShell>
  )
}
