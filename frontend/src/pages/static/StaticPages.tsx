import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { BookOpen, Bug, Building2, Clock3, Database, ExternalLink, FileText, GitBranch, Home, LifeBuoy, Lightbulb, Mail, MapPin, MessageSquareWarning, Phone, Workflow } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { api } from "@/lib/api"
import { appPath } from "@/lib/runtime-paths"
import { runtimeConfig } from "@/lib/runtime-config"
import { KnowledgebaseStatus } from "@/components/knowledgebase/KnowledgebaseStatus"
import { databaseLogo } from "@/lib/database-logos"

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
  const orgName = organization.name || runtimeConfig.organizationName

  return (
    <PageShell
      eyebrow="Contact"
      title="Contact and Support"
      description={`Support channels, service hours, and public resources for ${orgName}.`}
    >
      <section className="space-y-3">
        {isLoading ? (
          <AppLoader label="Loading contact information" />
        ) : null}

        <ContentSection
          icon={LifeBuoy}
          title="Support channels"
          description="Choose the clinical, sample, or platform channel that matches the request."
          aside={<HoursSummary hours={hours} />}
          tone="primary"
          bodyClassName="flex flex-wrap gap-3 p-3"
        >
            {contacts.length ? contacts.map((contact, index) => (
              <ContactCard key={`${contact.label}-${index}`} contact={contact} tone={STATIC_TONES[index % STATIC_TONES.length]} />
            )) : (
              <div className="min-w-full flex-1 rounded-lg border border-dashed border-border bg-muted/25 p-4 type-body-sm text-muted-foreground">No contact channels are configured yet.</div>
            )}
        </ContentSection>

        <ContentSection
          icon={Building2}
          title="Center and service details"
          description="Deployment ownership, central contacts, location, and related resources."
          tone="info"
          bodyClassName="flex flex-wrap gap-3 p-3"
        >
            <OrganizationCard organization={organization} fallbackName={orgName} />
            <SupportCard support={support} />
            <AddressCard organization={organization} />
            <UsefulLinksCard links={links} />
            <Link
              to="/about"
              className="static-info-card flex min-w-full flex-1 flex-col justify-between gap-3 p-4 md:min-w-80 md:basis-96"
              data-static-tone="primary"
            >
              <div>
                <DetailHeading icon={Building2} title="Application and deployment" />
                <p className="mt-2 type-body-sm text-muted-foreground">
                  Review application, reference database, pipeline, and knowledgebase versions.
                </p>
              </div>
              <span className="inline-flex items-center gap-2 type-body-sm font-semibold text-link">
                Open deployment details
                <ExternalLink className="size-4" />
              </span>
            </Link>
        </ContentSection>
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
  const links = data?.links || []
  const codebase = data?.codebase || {}
  const application = data?.application || {}
  const software = data?.software || {}
  const references = data?.references || {}
  const databases = data?.databases || {}
  const softwareLinks = data?.software_links || []
  const orgName = organization.name || runtimeConfig.organizationName
  const pipelines = software.pipelines || {}
  const sampleReferenceVersions = references.sample_database_versions || {}
  const aboutLinks = buildAboutLinks([...links, ...softwareLinks], codebase)

  return (
    <PageShell
      eyebrow="About"
      title="Coyote3"
      description={`Application, reference, version, and support information for ${orgName}.`}
      actions={
        <>
          <Link to="/public/catalog" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <Home className="size-4" />
            Catalog
          </Link>
          <Link to="/contact" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <LifeBuoy className="size-4" />
            Contact
          </Link>
          {codebase.license_url ? (
            <a href={codebase.license_url} target="_blank" rel="noreferrer" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
              <ExternalLink className="size-4" />
              License
            </a>
          ) : null}
        </>
      }
    >
      <section className="space-y-3">
        {isLoading ? (
          <AppLoader label="Loading application information" />
        ) : null}

        <ContentSection
          icon={Workflow}
          title="Clinical interpretation and reporting workspace"
          description={application.description || "Coyote3 brings assay-aware review, variant interpretation, knowledgebase context, and traceable report generation into one application."}
          tone="primary"
          bodyClassName="grid gap-px bg-border/60 sm:grid-cols-2 xl:grid-cols-4"
        >
          <InfoCard tone="primary" icon={GitBranch} label="Application version" value={application.version || "-"} hint={application.environment ? `Environment: ${application.environment}` : undefined} />
          <InfoCard tone="info" icon={Database} label="Primary database" value={databases.primary || "-"} hint={databases.bam_service ? `BAM service: ${databases.bam_service}` : undefined} />
          <InfoCard tone="success" icon={FileText} label="VEP metadata" value={references.vep_metadata?.length ? `${references.vep_metadata.length} version${references.vep_metadata.length === 1 ? "" : "s"}` : "None recorded"} hint="Observed in the VEP metadata collection." />
          <InfoCard tone="warning" icon={Building2} label="Deployment" value={orgName} hint={organization.department || "Center-managed Coyote3 deployment"} />
        </ContentSection>

        <ContentSection
          icon={Database}
          title="Reference and software versions"
          description="Versions observed in loaded samples and configured external services."
          tone="info"
          bodyClassName="grid gap-3 p-3 xl:grid-cols-4"
        >
            <VersionBlock icon={GitBranch} tone="primary" className="xl:col-span-2" title="Analysis pipelines" values={pipelines} empty="No pipeline versions observed in loaded samples." />
            <VersionBlock icon={Database} showDatabaseLogos tone="info" className="xl:col-span-2" title="Sample reference databases" values={sampleReferenceVersions} empty="No sample database versions recorded yet." />
            <VersionBlock icon={FileText} tone="success" title="VEP metadata versions" values={{ vep_metadata: references.vep_metadata || [] }} empty="No VEP metadata versions recorded yet." />
            <VersionBlock icon={ExternalLink} showDatabaseLogos tone="warning" className="xl:col-span-3" title="External knowledgebases" values={databases.knowledgebases || {}} empty="No external knowledgebase endpoints configured." />
        </ContentSection>

        <ContentSection
          icon={Database}
          title="Installed knowledgebase releases"
          description="Locally indexed products and configured external services."
          tone="success"
          bodyClassName=""
        >
          <KnowledgebaseStatus payload={data?.knowledgebase_status} />
        </ContentSection>

        <ContentSection
          icon={ExternalLink}
          title="Resources and support"
          description="Documentation, source, licensing, and service contacts."
          tone="warning"
          bodyClassName="flex flex-wrap gap-3 p-3"
        >
            {aboutLinks.map((link) => (
              <ResourceLink key={`${link.label}-${link.url}`} link={link} />
            ))}
            <Link to="/contact" className="static-info-card flex min-w-full flex-1 items-start gap-2 p-4 type-body-sm text-link sm:min-w-80 sm:basis-96" data-static-tone="primary">
              <LifeBuoy className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>
                Contact and support
                <span className="block type-caption text-muted-foreground">Service hours, support channels, and escalation details.</span>
              </span>
            </Link>
        </ContentSection>
      </section>
    </PageShell>
  )
}

type ContactPerson = { name?: string; email: string }
type ContactChannel = {
  label?: string
  role?: string
  description?: string
  email?: string
  phone?: string
  people?: ContactPerson[]
}

type PublicContactPayload = {
  organization: Record<string, string>
  support: Record<string, string>
  codebase?: Record<string, string>
  contacts: ContactChannel[]
  links: Array<Record<string, string>>
  hours: Array<Record<string, string>>
}

type PublicAboutPayload = PublicContactPayload & {
  application: Record<string, any>
  references: Record<string, any>
  software: Record<string, any>
  databases: Record<string, any>
  software_links?: LinkLike[]
  knowledgebase_status?: import("@/components/knowledgebase/KnowledgebaseStatus").KnowledgebaseStatusPayload
}

type LinkLike = Record<string, string>
type StaticTone = "primary" | "info" | "success" | "warning"

const STATIC_TONES: StaticTone[] = ["primary", "info", "success", "warning"]

function ContactCard({ contact, tone }: { contact: ContactChannel; tone: StaticTone }) {
  const people = contact.people || (contact.email ? [{ email: contact.email }] : [])
  return (
    <article className="static-info-card min-w-full flex-1 p-4 sm:min-w-80 sm:basis-96" data-static-tone={tone}>
      {contact.role ? <p className="type-page-eyebrow text-primary">{contact.role}</p> : null}
      <p className="type-card-title mt-0.5 text-foreground">{contact.label}</p>
      {contact.description ? <p className="type-body-sm mt-1.5 text-muted-foreground">{contact.description}</p> : null}
      <div className="mt-3 space-y-1.5 type-body-sm">
        {people.map((person) => (
          <a key={person.email} className="link-text flex items-start gap-2 font-semibold" href={`mailto:${person.email}`}>
            <Mail className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{person.name ? `${person.name} (${person.email})` : person.email}</span>
          </a>
        ))}
        {contact.phone ? (
          <a className="link-text flex items-center gap-2 font-semibold" href={`tel:${contact.phone}`}>
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
    <div className="static-info-card min-w-full flex-1 p-4 md:min-w-80 md:basis-96" data-static-tone="success">
      <DetailHeading icon={LifeBuoy} title="Central support" />
      <div className="mt-2 space-y-1.5 type-body-sm">
        {support.primary_email ? (
          <a className="link-text flex items-center gap-2 font-semibold" href={`mailto:${support.primary_email}`}>
            <Mail className="h-4 w-4" />
            {support.primary_email}
          </a>
        ) : null}
        {support.urgent_phone ? (
          <a className="link-text flex items-center gap-2 font-semibold" href={`tel:${support.urgent_phone}`}>
            <Phone className="h-4 w-4" />
            {support.urgent_phone}
          </a>
        ) : null}
      </div>
    </div>
  )
}

function OrganizationCard({ organization, fallbackName }: { organization: Record<string, string>; fallbackName: string }) {
  return (
    <section className="static-info-card min-w-full flex-1 p-4 md:min-w-80 md:basis-96" data-static-tone="primary">
      <DetailHeading icon={Building2} title={fallbackName} />
      {organization.department ? <p className="type-label mt-2 uppercase text-muted-foreground">{organization.department}</p> : null}
      {organization.description ? <p className="type-body-sm mt-2 text-muted-foreground">{organization.description}</p> : null}
    </section>
  )
}

function HoursSummary({ hours }: { hours: Array<Record<string, string>> }) {
  if (!hours.length) return null
  return (
    <dl className="flex flex-wrap gap-2 lg:justify-end">
        {hours.map((item) => (
          <div key={`${item.label}-${item.value}`} className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 py-2">
            <Clock3 className="size-4 shrink-0 text-primary" />
            <div>
              <dt className="type-label text-muted-foreground">{item.label}</dt>
              <dd className="type-meta text-foreground">{item.value}</dd>
            </div>
          </div>
        ))}
    </dl>
  )
}

function AddressCard({ organization }: { organization: Record<string, string> }) {
  if (!organization.address) return null
  return (
    <div className="static-info-card min-w-full flex-1 p-4 type-body-sm md:min-w-80 md:basis-96" data-static-tone="warning">
      <DetailHeading icon={MapPin} title="Address" />
      <p className="mt-2 whitespace-pre-line text-muted-foreground">{organization.address}</p>
    </div>
  )
}

function UsefulLinksCard({ links }: { links: LinkLike[] }) {
  if (!links.length) return null
  return (
    <div className="static-info-card min-w-full flex-1 p-4 md:min-w-80 md:basis-96" data-static-tone="info">
      <DetailHeading icon={ExternalLink} title="Useful links" />
      <div className="mt-1">
        {links.map((link) => <ResourceLink key={`${link.label}-${link.url}`} link={link} embedded />)}
      </div>
    </div>
  )
}

function ResourceLink({ link, embedded = false }: { link: LinkLike; embedded?: boolean }) {
  const Icon =
    link.icon === "bug" ? Bug :
    link.icon === "feature" ? Lightbulb :
    link.icon === "issue" ? MessageSquareWarning :
    link.icon === "docs" ? BookOpen :
    link.icon === "external" ? Workflow :
    ExternalLink
  return (
    <a
      href={publicHref(link.url)}
      target={isExternalHref(link.url) ? "_blank" : undefined}
      rel={isExternalHref(link.url) ? "noreferrer" : undefined}
      className={embedded
        ? "flex items-start gap-2 border-b border-border/70 px-1 py-2 type-body-sm last:border-b-0 hover:text-link"
        : "static-info-card flex min-w-full flex-1 basis-96 items-start gap-2 p-4 type-body-sm sm:min-w-80"}
      data-static-tone={embedded ? undefined : "info"}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <span>
        {link.label}
        {link.description ? <span className="block text-xs font-medium text-muted-foreground">{link.description}</span> : null}
      </span>
    </a>
  )
}

function InfoCard({ icon: Icon, label, value, hint, tone }: { icon: any; label: string; value: string; hint?: string; tone: StaticTone }) {
  return (
    <article className="static-metric flex min-w-0 items-start gap-3 bg-card p-4" data-static-tone={tone}>
      <div className="static-icon flex size-8 shrink-0 items-center justify-center rounded-lg"><Icon className="size-4" /></div>
      <div className="min-w-0">
        <p className="type-label text-muted-foreground">{label}</p>
        <p className="type-body-sm mt-0.5 break-words text-foreground">{value}</p>
        {hint ? <p className="type-caption mt-0.5 break-words text-muted-foreground">{hint}</p> : null}
      </div>
    </article>
  )
}

function VersionBlock({ icon: Icon, title, values, empty, tone, showDatabaseLogos = false, className = "" }: { icon: LucideIcon; title: string; values: any; empty: string; tone: StaticTone; showDatabaseLogos?: boolean; className?: string }) {
  const entries = Object.entries(values || {}).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0
    return value !== undefined && value !== null && String(value).trim() !== ""
  })
  return (
    <div className={`static-info-card p-4 ${className}`} data-static-tone={tone}>
      <div className="mb-2 flex items-center gap-2">
        <span className="static-icon flex size-7 shrink-0 items-center justify-center rounded-md">
          <Icon className="size-3.5" />
        </span>
        <p className="type-card-title text-foreground">{title}</p>
      </div>
      {entries.length ? (
        <dl className="flex flex-wrap gap-2">
          {entries.map(([key, value]) => {
            const logo = showDatabaseLogos ? databaseLogo(key) : undefined
            return (
              <div key={key} className="flex min-w-36 max-w-full items-center gap-2 rounded-md bg-muted/60 px-2 py-1.5">
                {logo ? <img src={appPath(logo.src)} alt={logo.alt} className="max-h-5 w-12 shrink-0 object-contain" /> : null}
                <dt className="type-label shrink-0 text-muted-foreground">{humanLabel(key)}</dt>
                <dd className="flex min-w-0 flex-wrap gap-1">
                  {Array.isArray(value) ? value.map((item) => (
                    <span key={`${key}-${item}`} className="rounded-full border border-border bg-background px-2 py-0.5 type-label text-foreground">{String(item)}</span>
                  )) : <span className="break-all type-meta text-foreground">{String(value)}</span>}
                </dd>
              </div>
            )
          })}
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

function ContentSection({
  icon: Icon,
  title,
  description,
  tone,
  aside,
  bodyClassName = "p-4",
  children,
}: {
  icon: LucideIcon
  title: string
  description?: string
  tone: StaticTone
  aside?: ReactNode
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <section className="static-page-section overflow-hidden" data-static-tone={tone}>
      <header className="static-page-section-header flex flex-col gap-3 border-b border-border px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="static-icon mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md">
            <Icon className="size-4" />
          </span>
          <div className="min-w-0">
            <h2 className="type-card-title text-foreground">{title}</h2>
            {description ? <p className="mt-0.5 type-body-sm text-muted-foreground">{description}</p> : null}
          </div>
        </div>
        {aside}
      </header>
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

function DetailHeading({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 shrink-0 text-primary" />
      <h3 className="type-card-title text-foreground">{title}</h3>
    </div>
  )
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
