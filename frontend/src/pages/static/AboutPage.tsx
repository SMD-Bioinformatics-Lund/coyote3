import { KnowledgebaseStatus } from "@/components/knowledgebase/KnowledgebaseStatus"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { runtimeConfig } from "@/lib/runtime-config"
import { useQuery } from "@tanstack/react-query"
import { BookOpen, Building2, Database, ExternalLink, FileText, GitBranch, Home, LifeBuoy, Workflow } from "lucide-react"
import { Link } from "react-router-dom"
import { ContentSection, InfoCard, ResourceLink, VersionBlock } from "./static-content"
import { buildAboutLinks, type PublicAboutPayload } from "./static-values"

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
          <Link to="/about/vep" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <BookOpen className="size-4" />VEP reference
          </Link>
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
          <InfoCard
            tone="info"
            icon={Database}
            label="Primary database"
            value={databases.primary || "-"}
            hint={[
              databases.identity ? `Identity: ${databases.identity}` : "",
              databases.bam_service ? `BAM service: ${databases.bam_service}` : "",
            ].filter(Boolean).join(" | ") || undefined}
          />
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
          bodyClassName="grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3"
        >
            {aboutLinks.map((link) => (
              <ResourceLink key={`${link.label}-${link.url}`} link={link} embedded />
            ))}
            <Link to="/contact" className="flex min-w-0 items-start gap-2 px-1 py-2 type-body-sm text-link">
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
