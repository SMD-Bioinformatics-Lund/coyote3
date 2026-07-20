import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { BookOpen, Bug, Building2, Database, ExternalLink, FileText, GitBranch, Home, LifeBuoy, Lightbulb, Mail, MapPin, MessageSquareWarning, Phone } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { api } from "@/lib/api"
import { appPath } from "@/lib/runtime-paths"

export function ContactPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["public-contact"],
    queryFn: () => api.get<PublicContactPayload>("/public/contact").then((res) => res.data),
    staleTime: 10 * 60 * 1000,
  })

  const organization = data?.organization || {}
  const contacts = data?.contacts || []
  const hours = data?.hours || []
  const links = data?.links || []
  const support = data?.support || {}
  const orgName = organization.name || import.meta.env.VITE_ORGANIZATION_NAME || "Coyote3"

  return (
    <PageShell
      eyebrow="Contact"
      title="Contact and Support"
      description={`Support channels, service hours, and public resources for ${orgName}.`}
    >
      <section className="surface-panel p-5">
        {isLoading ? (
          <AppLoader label="Loading contact information" />
        ) : null}

        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary"><LifeBuoy className="h-5 w-5" /></div>
            <div>
              <h2 className="text-lg font-bold">{orgName}</h2>
              <p className="text-sm text-muted-foreground">
                {organization.description || "Clinical genomics interpretation and reporting support."}
              </p>
              {organization.department ? (
                <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {organization.department}
                </p>
              ) : null}
            </div>
          </div>
          <Link to="/about" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <Building2 className="h-4 w-4" />
            About Coyote3
          </Link>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.45fr)]">
          <section className="rounded-xl border border-border bg-background/70 p-4">
            <div className="mb-3 flex items-center gap-2">
              <Mail className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-black uppercase tracking-wide text-muted-foreground">Support Channels</h3>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {contacts.length ? contacts.map((contact) => (
                <ContactCard key={contact.label} contact={contact} />
              )) : (
                <p className="text-sm text-muted-foreground">No contact channels are configured yet.</p>
              )}
            </div>
          </section>

          <aside className="space-y-3">
            <SupportCard support={support} />
            <HoursCard hours={hours} />
            <AddressCard organization={organization} />
            <UsefulLinksCard links={links} />
          </aside>
        </div>
      </section>
    </PageShell>
  )
}

export function AboutPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["public-about"],
    queryFn: () => api.get<PublicAboutPayload>("/public/about").then((res) => res.data),
    staleTime: 10 * 60 * 1000,
  })

  const organization = data?.organization || {}
  const hours = data?.hours || []
  const links = data?.links || []
  const support = data?.support || {}
  const codebase = data?.codebase || {}
  const application = data?.application || {}
  const software = data?.software || {}
  const references = data?.references || {}
  const databases = data?.databases || {}
  const orgName = organization.name || import.meta.env.VITE_ORGANIZATION_NAME || "Coyote3"
  const pipelines = software.pipelines || {}
  const sampleReferenceVersions = references.sample_database_versions || {}
  const aboutLinks = buildAboutLinks(links, codebase)

  return (
    <PageShell
      eyebrow="About"
      title="Coyote3"
      description={`Application, reference, version, and support information for ${orgName}.`}
    >
      <section className="surface-panel p-5">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary"><Building2 className="h-5 w-5" /></div>
            <div>
              <h2 className="text-lg font-bold">{orgName}</h2>
              <p className="text-sm text-muted-foreground">
                {organization.description || application.description || "Clinical genomics interpretation and reporting workspace."}
              </p>
              {organization.department ? (
                <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {organization.department}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/public/catalog" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
              <Home className="h-4 w-4" />
              Catalog
            </Link>
            <Link to="/contact" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
              <LifeBuoy className="h-4 w-4" />
              Contact
            </Link>
            {codebase.license_url ? (
              <a
                href={codebase.license_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
              >
                <ExternalLink className="h-4 w-4" />
                License
              </a>
            ) : null}
          </div>
        </div>

        {isLoading ? (
          <AppLoader label="Loading application information" />
        ) : null}

        <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <InfoCard icon={GitBranch} label="Application Version" value={application.version || "-"} hint={application.environment ? `Environment: ${application.environment}` : undefined} />
          <InfoCard icon={Database} label="Primary Database" value={databases.primary || "-"} hint={databases.bam_service ? `BAM service: ${databases.bam_service}` : undefined} />
          <InfoCard icon={FileText} label="VEP Versions" value={formatList(software.vep)} hint={formatList(references.vep_metadata, "No VEP metadata versions")} />
          <InfoCard icon={LifeBuoy} label="Support" value={support.primary_email || "Configured by center"} hint={support.urgent_phone || undefined} />
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <div className="space-y-4">
            <section className="rounded-xl border border-border bg-background/70 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-black uppercase tracking-wide text-muted-foreground">Reference and Software Versions</h3>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <VersionBlock title="Analysis Pipelines" values={pipelines} empty="No pipeline versions observed in loaded samples." />
                <VersionBlock title="Sample Reference Databases" values={sampleReferenceVersions} empty="No sample database versions recorded yet." />
                <VersionBlock title="External Knowledgebases" values={databases.knowledgebases || {}} empty="No external knowledgebase endpoints configured." />
              </div>
            </section>

            <section className="rounded-xl border border-border bg-background/70 p-4">
              <div className="mb-3 flex items-center gap-2">
                <ExternalLink className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-black uppercase tracking-wide text-muted-foreground">Useful Links</h3>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {aboutLinks.map((link) => (
                  <ResourceLink key={`${link.label}-${link.url}`} link={link} />
                ))}
              </div>
            </section>
          </div>

          <aside className="space-y-3">
            <SupportCard support={support} />
            <HoursCard hours={hours} />
            <AddressCard organization={organization} />
          </aside>
        </div>
      </section>
    </PageShell>
  )
}

type PublicContactPayload = {
  organization: Record<string, string>
  support: Record<string, string>
  codebase?: Record<string, string>
  contacts: Array<Record<string, string>>
  links: Array<Record<string, string>>
  hours: Array<Record<string, string>>
}

type PublicAboutPayload = PublicContactPayload & {
  application: Record<string, any>
  references: Record<string, any>
  software: Record<string, any>
  databases: Record<string, any>
}

type LinkLike = Record<string, string>

function ContactCard({ contact }: { contact: Record<string, string> }) {
  return (
    <article className="rounded-xl border border-border bg-background/70 p-4">
      <p className="text-sm font-bold text-foreground">{contact.label}</p>
      {contact.role ? <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{contact.role}</p> : null}
      {contact.description ? <p className="mt-3 text-sm leading-6 text-muted-foreground">{contact.description}</p> : null}
      <div className="mt-4 space-y-2 text-sm">
        {contact.email ? (
          <a className="flex items-center gap-2 font-semibold text-primary hover:underline" href={`mailto:${contact.email}`}>
            <Mail className="h-4 w-4" />
            {contact.email}
          </a>
        ) : null}
        {contact.phone ? (
          <a className="flex items-center gap-2 font-semibold text-primary hover:underline" href={`tel:${contact.phone}`}>
            <Phone className="h-4 w-4" />
            {contact.phone}
          </a>
        ) : null}
      </div>
    </article>
  )
}

function SupportCard({ support }: { support: Record<string, string> }) {
  if (!support.primary_email && !support.urgent_phone) return null
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4">
      <p className="text-sm font-bold">Primary Support</p>
      <div className="mt-3 space-y-2 text-sm">
        {support.primary_email ? (
          <a className="flex items-center gap-2 font-semibold text-primary hover:underline" href={`mailto:${support.primary_email}`}>
            <Mail className="h-4 w-4" />
            {support.primary_email}
          </a>
        ) : null}
        {support.urgent_phone ? (
          <a className="flex items-center gap-2 font-semibold text-primary hover:underline" href={`tel:${support.urgent_phone}`}>
            <Phone className="h-4 w-4" />
            {support.urgent_phone}
          </a>
        ) : null}
      </div>
    </div>
  )
}

function HoursCard({ hours }: { hours: Array<Record<string, string>> }) {
  if (!hours.length) return null
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4">
      <p className="text-sm font-bold">Service Hours</p>
      <dl className="mt-3 space-y-2 text-sm">
        {hours.map((item) => (
          <div key={`${item.label}-${item.value}`} className="grid grid-cols-[110px_1fr] gap-3">
            <dt className="font-semibold text-muted-foreground">{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function AddressCard({ organization }: { organization: Record<string, string> }) {
  if (!organization.address) return null
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4 text-sm">
      <p className="flex items-center gap-2 font-bold"><MapPin className="h-4 w-4 text-primary" /> Address</p>
      <p className="mt-2 whitespace-pre-line text-muted-foreground">{organization.address}</p>
    </div>
  )
}

function UsefulLinksCard({ links }: { links: LinkLike[] }) {
  if (!links.length) return null
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4">
      <p className="text-sm font-bold">Useful Links</p>
      <div className="mt-3 space-y-2">
        {links.map((link) => <ResourceLink key={`${link.label}-${link.url}`} link={link} />)}
      </div>
    </div>
  )
}

function ResourceLink({ link }: { link: LinkLike }) {
  const Icon =
    link.icon === "bug" ? Bug :
    link.icon === "feature" ? Lightbulb :
    link.icon === "issue" ? MessageSquareWarning :
    link.icon === "docs" ? BookOpen :
    ExternalLink
  return (
    <a
      href={publicHref(link.url)}
      target={isExternalHref(link.url) ? "_blank" : undefined}
      rel={isExternalHref(link.url) ? "noreferrer" : undefined}
      className="flex items-start gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold hover:bg-muted"
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <span>
        {link.label}
        {link.description ? <span className="block text-xs font-medium text-muted-foreground">{link.description}</span> : null}
      </span>
    </a>
  )
}

function InfoCard({ icon: Icon, label, value, hint }: { icon: any; label: string; value: string; hint?: string }) {
  return (
    <article className="rounded-xl border border-border bg-background/70 p-4">
      <div className="mb-3 flex items-center gap-2">
        <div className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="h-4 w-4" /></div>
        <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</p>
      </div>
      <p className="break-words text-sm font-bold text-foreground">{value}</p>
      {hint ? <p className="mt-1 break-words text-xs text-muted-foreground">{hint}</p> : null}
    </article>
  )
}

function VersionBlock({ title, values, empty }: { title: string; values: any; empty: string }) {
  const entries = Object.entries(values || {}).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0
    return value !== undefined && value !== null && String(value).trim() !== ""
  })
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <p className="mb-2 text-xs font-black uppercase tracking-wide text-muted-foreground">{title}</p>
      {entries.length ? (
        <dl className="space-y-2 text-sm">
          {entries.map(([key, value]) => (
            <div key={key} className="grid grid-cols-[minmax(110px,0.42fr)_minmax(0,1fr)] gap-3">
              <dt className="break-words font-semibold text-muted-foreground">{humanLabel(key)}</dt>
              <dd className="break-words font-semibold text-foreground">{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  )
}

function humanLabel(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatList(value: unknown, empty = "None recorded") {
  if (Array.isArray(value) && value.length) return value.join(", ")
  return empty
}

function buildAboutLinks(configuredLinks: LinkLike[], codebase: Record<string, string>) {
  const defaults: LinkLike[] = [
    {
      label: "User documentation",
      url: "/docs-site/",
      description: "Clinical user guide, deployment notes, and operating procedures.",
      icon: "docs",
    },
    codebase.license_url ? {
      label: "License",
      url: codebase.license_url,
      description: "Project license and deployment notices.",
    } : null,
    codebase.repository_url ? {
      label: "GitHub repository",
      url: codebase.repository_url,
      description: "Source repository, code review, and release history.",
      icon: "github",
    } : null,
    codebase.bug_report_url ? {
      label: "Report a Bug",
      url: codebase.bug_report_url,
      description: "Report an application defect or reproducible malfunction.",
      icon: "bug",
    } : null,
    codebase.feature_request_url ? {
      label: "Request a Feature",
      url: codebase.feature_request_url,
      description: "Suggest a product improvement or workflow enhancement.",
      icon: "feature",
    } : null,
    codebase.support_request_url ? {
      label: "Support",
      url: codebase.support_request_url,
      description: "Ask for help with setup, usage, access, or operational behavior.",
      icon: "issue",
    } : null,
  ].filter(Boolean) as LinkLike[]
  const byUrl = new Map<string, LinkLike>()
  for (const link of [...defaults, ...configuredLinks]) {
    if (!link.url) continue
    byUrl.set(link.url, link)
  }
  return Array.from(byUrl.values())
}

function publicHref(url?: string) {
  if (!url) return "#"
  if (/^https?:\/\//i.test(url) || url.startsWith("mailto:") || url.startsWith("tel:")) return url
  return appPath(url)
}

function isExternalHref(url?: string) {
  return Boolean(url && /^https?:\/\//i.test(url))
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
