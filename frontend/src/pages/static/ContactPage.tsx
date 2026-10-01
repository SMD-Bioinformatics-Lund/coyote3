import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { runtimeConfig } from "@/lib/runtime-config"
import { useQuery } from "@tanstack/react-query"
import { Building2, ExternalLink, LifeBuoy } from "lucide-react"
import { Link } from "react-router-dom"
import { AddressCard, ContactCard, ContentSection, DetailHeading, HoursSummary, OrganizationCard, SupportCard, UsefulLinksCard } from "./static-content"
import { STATIC_TONES, type PublicContactPayload } from "./static-values"

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
