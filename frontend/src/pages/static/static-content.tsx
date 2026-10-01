import { databaseLogo } from "@/lib/database-logos"
import { appPath } from "@/lib/runtime-paths"
import type { LucideIcon } from "lucide-react"
import { BookOpen, Bug, Building2, Clock3, ExternalLink, LifeBuoy, Lightbulb, Mail, MapPin, MessageSquareWarning, Phone, Workflow } from "lucide-react"
import type { ReactNode } from "react"
import { humanLabel, isExternalHref, publicHref, type ContactChannel, type LinkLike, type StaticTone } from "./static-values"

export function ContactCard({ contact, tone }: { contact: ContactChannel; tone: StaticTone }) {
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

export function SupportCard({ support }: { support: Record<string, string> }) {
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

export function OrganizationCard({ organization, fallbackName }: { organization: Record<string, string>; fallbackName: string }) {
  return (
    <section className="static-info-card min-w-full flex-1 p-4 md:min-w-80 md:basis-96" data-static-tone="primary">
      <DetailHeading icon={Building2} title={fallbackName} />
      {organization.department ? <p className="type-label mt-2 uppercase text-muted-foreground">{organization.department}</p> : null}
      {organization.description ? <p className="type-body-sm mt-2 text-muted-foreground">{organization.description}</p> : null}
    </section>
  )
}

export function HoursSummary({ hours }: { hours: Array<Record<string, string>> }) {
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

export function AddressCard({ organization }: { organization: Record<string, string> }) {
  if (!organization.address) return null
  return (
    <div className="static-info-card min-w-full flex-1 p-4 type-body-sm md:min-w-80 md:basis-96" data-static-tone="warning">
      <DetailHeading icon={MapPin} title="Address" />
      <p className="mt-2 whitespace-pre-line text-muted-foreground">{organization.address}</p>
    </div>
  )
}

export function UsefulLinksCard({ links }: { links: LinkLike[] }) {
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

export function ResourceLink({ link, embedded = false }: { link: LinkLike; embedded?: boolean }) {
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

export function InfoCard({ icon: Icon, label, value, hint, tone }: { icon: any; label: string; value: string; hint?: string; tone: StaticTone }) {
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

export function VersionBlock({ icon: Icon, title, values, empty, tone, showDatabaseLogos = false, className = "" }: { icon: LucideIcon; title: string; values: any; empty: string; tone: StaticTone; showDatabaseLogos?: boolean; className?: string }) {
  const entries = Object.entries(values || {}).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0
    return value !== undefined && value !== null && String(value).trim() !== ""
  })
  return (
    <div className={`min-w-0 border-b border-border p-3 ${className}`} data-static-tone={tone}>
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

export function ContentSection({
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
    <section aria-label={title} className="glass-card min-w-0 overflow-hidden" data-static-tone={tone}>
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

export function DetailHeading({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 shrink-0 text-primary" />
      <h3 className="type-card-title text-foreground">{title}</h3>
    </div>
  )
}
