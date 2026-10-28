import { KnowledgebaseStatus } from "@/components/knowledgebase/KnowledgebaseStatus"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { runtimeConfig } from "@/lib/runtime-config"
import { useQuery } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
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
  const vepMetadataVersions = [...(references.vep_metadata || [])].sort((left, right) =>
    String(left).localeCompare(String(right), undefined, { numeric: true }),
  )
  const aboutLinks = buildAboutLinks([...links, ...softwareLinks], codebase)

  return (
    <PageShell
      className="material-page static-material-page"
      eyebrow="About"
      title="Coyote3"
      description={`Application, reference, version, and support information for ${orgName}.`}
      actions={
        <>
          <Link to="/about/vep" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <icon.bookOpen className="size-4" />VEP reference
          </Link>
          <Link to="/public/catalog" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <icon.home className="size-4" />
            Catalog
          </Link>
          <Link to="/contact" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
            <icon.lifeBuoy className="size-4" />
            Contact
          </Link>
          {codebase.license_url ? (
            <a href={codebase.license_url} target="_blank" rel="noreferrer" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm">
              <icon.externalLink className="size-4" />
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
          icon={icon.workflow}
          title="Clinical interpretation and reporting workspace"
          description={application.description || "Coyote3 brings assay-aware review, variant interpretation, knowledgebase context, and traceable report generation into one application."}
          tone="primary"
          bodyClassName="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <InfoCard tone="primary" icon={icon.gitBranch} label="Application version" value={application.version || "-"} hint={application.environment ? `Environment: ${application.environment}` : undefined}
            details={[{ label: "Core SDK", value: application.sdk_version || "Not installed" }, { label: "Python client SDK", value: application.client_sdk_version || "Not installed" }]} />
          <InfoCard
            tone="info"
            icon={icon.database}
            label="Primary database"
            value={databases.primary || "-"}
            details={[
              ...(databases.identity ? [{ label: "Identity", value: databases.identity }] : []),
              ...(databases.bam_service ? [{ label: "BAM service", value: databases.bam_service }] : []),
            ]}
          />
          <InfoCard tone="success" icon={icon.fileText} label="VEP metadata" value={references.vep_metadata?.length ? `${references.vep_metadata.length} version${references.vep_metadata.length === 1 ? "" : "s"}` : "None recorded"} hint="Observed in the VEP metadata collection." />
          <InfoCard tone="warning" icon={icon.building2} label="Deployment" value={orgName} hint={organization.department || "Center-managed Coyote3 deployment"} />
        </ContentSection>

        <ContentSection
          icon={icon.database}
          title="Reference and software versions"
          description="Versions observed in loaded samples and configured external services."
          tone="info"
          bodyClassName="grid gap-3 p-3 xl:grid-cols-4"
        >
            <VersionBlock icon={icon.gitBranch} tone="primary" className="xl:col-span-2" title="Analysis pipelines" values={pipelines} empty="No pipeline versions observed in loaded samples." />
            <VersionBlock icon={icon.database} showDatabaseLogos tone="info" className="xl:col-span-2" title="Sample reference databases" values={sampleReferenceVersions} empty="No sample database versions recorded yet." />
            <VersionBlock icon={icon.fileText} tone="success" title="VEP metadata versions" values={{ vep_metadata: vepMetadataVersions }} empty="No VEP metadata versions recorded yet." />
            <VersionBlock icon={icon.externalLink} showDatabaseLogos tone="warning" className="xl:col-span-3" title="External knowledgebases" values={databases.knowledgebases || {}} empty="No external knowledgebase endpoints configured." />
        </ContentSection>

        <ContentSection
          icon={icon.database}
          title="Installed knowledgebase releases"
          description="Locally indexed products and configured external services."
          tone="success"
          bodyClassName=""
        >
          <KnowledgebaseStatus payload={data?.knowledgebase_status} />
        </ContentSection>

        <ContentSection
          icon={icon.externalLink}
          title="Resources and support"
          description="Documentation, source, licensing, and service contacts."
          tone="warning"
          bodyClassName="grid gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3"
        >
            {aboutLinks.map((link) => (
              <ResourceLink key={`${link.label}-${link.url}`} link={link} />
            ))}
            <Link to="/contact" data-static-tone="primary" className="static-info-card flex min-w-0 items-start gap-2 p-4 type-body-sm text-link">
              <icon.lifeBuoy className="mt-0.5 size-4 shrink-0 text-primary" />
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
