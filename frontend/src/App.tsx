import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Suspense, lazy, type ReactNode } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AdminPermissionBoundary } from "./components/admin/AdminPermissionBoundary"
import { TablePreferencesProvider } from "./components/data-table/TablePreferencesProvider"
import { AppLoader } from "./components/layout/AppLoader"
import { Layout } from "./components/layout/Layout"
import { notify } from "./components/notifications/notification-store"
import { ADMIN_UTILITY_PERMISSIONS } from "./lib/access-control"
import type { ApplicationModuleKey } from "./lib/app-module-state"
import { ApplicationModuleBoundary } from "./lib/app-modules"
import { APP_BASENAME } from "./lib/runtime-paths"
import { Login } from "./pages/auth/Login"

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })))
const Samples = lazy(() => import("./pages/Samples").then((module) => ({ default: module.Samples })))
const SampleDetail = lazy(() => import("./pages/SampleDetail").then((module) => ({ default: module.SampleDetail })))
const VariantDetail = lazy(() => import("./pages/findings/VariantDetail").then((module) => ({ default: module.VariantDetail })))
const CNVDetail = lazy(() => import("./pages/findings/CNVDetail").then((module) => ({ default: module.CNVDetail })))
const FusionDetail = lazy(() => import("./pages/findings/FusionDetail").then((module) => ({ default: module.FusionDetail })))
const TranslocationDetail = lazy(() => import("./pages/findings/TranslocationDetail").then((module) => ({ default: module.TranslocationDetail })))
const ForgotPassword = lazy(() => import("./pages/auth/ForgotPasswordPage").then((module) => ({ default: module.ForgotPassword })))
const ResetPassword = lazy(() => import("./pages/auth/ResetPasswordPage").then((module) => ({ default: module.ResetPassword })))
const AdminHub = lazy(() => import("./pages/admin/AdminHubPage").then((module) => ({ default: module.AdminHubPage })))
const AssaySubpanelsPage = lazy(() => import("./pages/admin/AssaySubpanelsPage").then((module) => ({ default: module.AssaySubpanelsPage })))
const SubpanelDefinitionsPage = lazy(() => import("./pages/admin/SubpanelDefinitionsPage").then((module) => ({ default: module.SubpanelDefinitionsPage })))
const AssayGroupsPage = lazy(() => import("./pages/admin/AssayGroupsPage").then((module) => ({ default: module.AssayGroupsPage })))
const AssayEditorPage = lazy(() => import("./pages/admin/assays/AssayEditorPage").then((module) => ({ default: module.AssayEditorPage })))
const AssaysPage = lazy(() => import("./pages/admin/assays/AssaysPage").then((module) => ({ default: module.AssaysPage })))
const AssayConfigurationEditorPage = lazy(() => import("./pages/admin/assay-configurations/AssayConfigurationEditorPage").then((module) => ({ default: module.AssayConfigurationEditorPage })))
const AssayConfigurationsPage = lazy(() => import("./pages/admin/assay-configurations/AssayConfigurationsPage").then((module) => ({ default: module.AssayConfigurationsPage })))
const GeneListEditorPage = lazy(() => import("./pages/admin/gene-lists/GeneListEditorPage").then((module) => ({ default: module.GeneListEditorPage })))
const GeneListsPage = lazy(() => import("./pages/admin/gene-lists/GeneListsPage").then((module) => ({ default: module.GeneListsPage })))
const UserEditorPage = lazy(() => import("./pages/admin/users/UserEditorPage").then((module) => ({ default: module.UserEditorPage })))
const UsersPage = lazy(() => import("./pages/admin/users/UsersPage").then((module) => ({ default: module.UsersPage })))
const RoleEditorPage = lazy(() => import("./pages/admin/roles/RoleEditorPage").then((module) => ({ default: module.RoleEditorPage })))
const RolesPage = lazy(() => import("./pages/admin/roles/RolesPage").then((module) => ({ default: module.RolesPage })))
const PermissionEditorPage = lazy(() => import("./pages/admin/permissions/PermissionEditorPage").then((module) => ({ default: module.PermissionEditorPage })))
const PermissionsPage = lazy(() => import("./pages/admin/permissions/PermissionsPage").then((module) => ({ default: module.PermissionsPage })))
const AdminSampleEditorPage = lazy(() => import("./pages/admin/samples/AdminSampleEditorPage").then((module) => ({ default: module.AdminSampleEditorPage })))
const AdminSamplesPage = lazy(() => import("./pages/admin/samples/AdminSamplesPage").then((module) => ({ default: module.AdminSamplesPage })))
const AssaySetupPage = lazy(() => import("./pages/admin/AssaySetupPage").then((module) => ({ default: module.AssaySetupPage })))
const AdminAuditPage = lazy(() => import("./pages/admin/AdminAuditPage").then((module) => ({ default: module.AdminAuditPage })))
const AdminControlsPage = lazy(() => import("./pages/admin/AdminControlsPage").then((module) => ({ default: module.AdminControlsPage })))
const AdminIngestPage = lazy(() => import("./pages/admin/AdminIngestPage").then((module) => ({ default: module.AdminIngestPage })))
const AdminSchemasPage = lazy(() => import("./pages/admin/AdminSchemasPage"))
const DemoInstallationPage = lazy(() => import("./pages/admin/DemoInstallationPage"))
const PublicCatalog = lazy(() => import("./pages/catalog/PublicCatalogPage").then((module) => ({ default: module.PublicCatalog })))
const PublicCatalogMatrix = lazy(() => import("./pages/catalog/PublicCatalogMatrixPage").then((module) => ({ default: module.PublicCatalogMatrix })))
const TieredVariantContext = lazy(() => import("./pages/search/TieredVariantContext").then((module) => ({ default: module.TieredVariantContext })))
const TieredVariantSearch = lazy(() => import("./pages/search/TieredVariantSearch").then((module) => ({ default: module.TieredVariantSearch })))
const GeneCohortExplorer = lazy(() => import("./pages/search/GeneCohortExplorer").then((module) => ({ default: module.GeneCohortExplorer })))
const Profile = lazy(() => import("./pages/account/Profile").then((module) => ({ default: module.Profile })))
const ChangePassword = lazy(() => import("./pages/auth/ChangePassword").then((module) => ({ default: module.ChangePassword })))
const ContactPage = lazy(() => import("./pages/static/ContactPage").then((module) => ({ default: module.ContactPage })))
const AboutPage = lazy(() => import("./pages/static/AboutPage").then((module) => ({ default: module.AboutPage })))
const VepReferencePage = lazy(() => import("./pages/static/VepReferencePage"))
const KnowledgebaseDetails = lazy(() => import("./pages/KnowledgebaseDetails").then((module) => ({ default: module.KnowledgebaseDetails })))
const NotFoundPage = lazy(() => import("./pages/static/NotFoundPage").then((module) => ({ default: module.NotFoundPage })))
const CoverageBlacklistPage = lazy(() => import("./pages/resources/CoverageBlacklistPage").then((module) => ({ default: module.CoverageBlacklistPage })))
const GeneInfoPage = lazy(() => import("./pages/resources/GeneInfoPage").then((module) => ({ default: module.GeneInfoPage })))
const PublicAspGenesPage = lazy(() => import("./pages/resources/PublicAspGenesPage").then((module) => ({ default: module.PublicAspGenesPage })))
const PublicGenelistPage = lazy(() => import("./pages/resources/PublicGenelistPage").then((module) => ({ default: module.PublicGenelistPage })))
const ReportsPage = lazy(() => import("./pages/reports/ReportsPage").then((module) => ({ default: module.ReportsPage })))
const SavedReportPage = lazy(() => import("./pages/reports/SavedReportPage").then((module) => ({ default: module.SavedReportPage })))
const NotificationHistoryPage = lazy(() => import("./pages/account/NotificationHistoryPage").then((module) => ({ default: module.NotificationHistoryPage })))
const UiRouteAuditPage = lazy(() => import("./pages/admin/UiRouteAuditPage").then((module) => ({ default: module.UiRouteAuditPage })))
const AdminNotificationBroadcastPage = lazy(() => import("./pages/admin/AdminNotificationBroadcastPage").then((module) => ({ default: module.AdminNotificationBroadcastPage })))
const ClinicalRulesPage = lazy(() => import("./pages/admin/ClinicalRulesPage").then((module) => ({ default: module.ClinicalRulesPage })))
const QueryRulesPage = lazy(() => import("./pages/admin/QueryRulesPage").then((module) => ({ default: module.QueryRulesPage })))
const QueryRuleTestingPage = lazy(() => import("./pages/admin/QueryRuleTestingPage").then((module) => ({ default: module.QueryRuleTestingPage })))
const ClinicalRuleTestingPage = lazy(() => import("./pages/admin/ClinicalRuleTestingPage").then((module) => ({ default: module.ClinicalRuleTestingPage })))
const PublicAssayCatalogPage = lazy(() => import("./pages/admin/PublicAssayCatalogPage").then((module) => ({ default: module.PublicAssayCatalogPage })))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      if ((error as { notificationShown?: boolean })?.notificationShown) return
      notify({
        tone: "error",
        title: "Unable to load data",
        message: error instanceof Error ? error.message : "A data request failed.",
        source: query.queryKey.map(String).join(" / "),
      })
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      if ((error as { notificationShown?: boolean })?.notificationShown) return
      notify({
        tone: "error",
        title: "Action failed",
        message: error instanceof Error ? error.message : "The requested change could not be completed.",
      })
    },
  }),
})

function RouteFallback() {
  return <AppLoader />
}

function withRouteLoader(element: ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>
}

function withAdminPermission(element: ReactNode, permission: string) {
  return withRouteLoader(
    <AdminPermissionBoundary permission={permission}>{element}</AdminPermissionBoundary>
  )
}

function withModule(element: ReactNode, moduleKey: ApplicationModuleKey) {
  return withRouteLoader(
    <ApplicationModuleBoundary moduleKey={moduleKey}>{element}</ApplicationModuleBoundary>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={APP_BASENAME || undefined}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/change-password" element={withRouteLoader(<ChangePassword />)} />
          <Route path="/forgot-password" element={withRouteLoader(<ForgotPassword />)} />
          <Route path="/reset-password" element={withRouteLoader(<ResetPassword />)} />
          <Route element={<TablePreferencesProvider><Layout /></TablePreferencesProvider>}>
            <Route path="/" element={withRouteLoader(<Dashboard />)} />
            <Route path="/samples" element={withRouteLoader(<Samples />)} />
            <Route path="/samples/:id" element={withRouteLoader(<SampleDetail />)} />
            <Route path="/samples/:id/variant/:varId" element={withModule(<VariantDetail />, "dna_analysis")} />
            <Route path="/samples/:id/cnv/:varId" element={withModule(<CNVDetail />, "dna_analysis")} />
            <Route path="/samples/:id/fusion/:varId" element={withModule(<FusionDetail />, "rna_analysis")} />
            <Route path="/samples/:id/translocation/:varId" element={withModule(<TranslocationDetail />, "dna_analysis")} />
            <Route path="/samples/:id/reports/:reportId" element={withModule(<SavedReportPage />, "reports")} />
            <Route path="/variants" element={withModule(<TieredVariantSearch />, "variant_search")} />
            <Route path="/variants/search" element={withModule(<TieredVariantSearch />, "variant_search")} />
            <Route path="/variants/gene-cohort" element={withModule(<GeneCohortExplorer />, "variant_search")} />
            <Route path="/variants/reported/:variantId/:tier" element={withModule(<TieredVariantContext />, "variant_search")} />
            <Route path="/reports" element={withModule(<ReportsPage />, "reports")} />
            <Route path="/notifications" element={withRouteLoader(<NotificationHistoryPage />)} />
            <Route path="/about" element={withRouteLoader(<AboutPage />)} />
            <Route path="/about/vep" element={withRouteLoader(<VepReferencePage />)} />
            <Route path="/knowledgebases" element={withModule(<KnowledgebaseDetails />, "knowledgebases")} />
            <Route path="/contact" element={withRouteLoader(<ContactPage />)} />
            <Route path="/public" element={withModule(<PublicCatalog />, "assay_catalog")} />
            <Route path="/public/catalog" element={withModule(<PublicCatalog />, "assay_catalog")} />
            <Route path="/public/matrix" element={withModule(<PublicCatalogMatrix />, "assay_catalog")} />
            <Route path="/public/genelists/:genelistId/view" element={withModule(<PublicGenelistPage />, "assay_catalog")} />
            <Route path="/public/asp/:aspId/genes" element={withModule(<PublicAspGenesPage />, "assay_catalog")} />
            <Route path="/public/gene/:geneId/info" element={withModule(<GeneInfoPage />, "knowledgebases")} />
            <Route path="/coverage/blacklisted/:group" element={withModule(<CoverageBlacklistPage />, "dna_analysis")} />
            <Route path="/admin" element={withRouteLoader(<AdminHub />)} />
            <Route path="/admin/audit" element={withAdminPermission(<AdminAuditPage />, ADMIN_UTILITY_PERMISSIONS.auditView)} />
            <Route path="/admin/controls" element={withAdminPermission(<AdminControlsPage />, ADMIN_UTILITY_PERMISSIONS.controlsView)} />
            <Route path="/admin/ingest" element={withModule(
              <AdminPermissionBoundary permission={ADMIN_UTILITY_PERMISSIONS.ingestManage}><AdminIngestPage /></AdminPermissionBoundary>,
              "ingest_workspace",
            )} />
            <Route path="/admin/schemas" element={withAdminPermission(<AdminSchemasPage />, ADMIN_UTILITY_PERMISSIONS.schemasView)} />
            <Route path="/admin/demo-installation" element={withAdminPermission(<DemoInstallationPage />, ADMIN_UTILITY_PERMISSIONS.demoInstall)} />
            <Route path="/admin/ui-routes" element={withAdminPermission(<UiRouteAuditPage />, ADMIN_UTILITY_PERMISSIONS.uiRouteAuditView)} />
            <Route path="/admin/notifications" element={withAdminPermission(<AdminNotificationBroadcastPage />, ADMIN_UTILITY_PERMISSIONS.broadcastCreate)} />
            <Route path="/admin/clinical-rules" element={withAdminPermission(<ClinicalRulesPage />, ADMIN_UTILITY_PERMISSIONS.clinicalRulesView)} />
            <Route path="/admin/query-rules" element={withAdminPermission(<QueryRulesPage />, "query_rules:view")} />
            <Route path="/admin/query-rules/testing" element={withAdminPermission(<QueryRuleTestingPage />, "query_rules:test")} />
            <Route path="/admin/clinical-rules/testing" element={withAdminPermission(<ClinicalRuleTestingPage />, ADMIN_UTILITY_PERMISSIONS.clinicalRulesTest)} />
            <Route path="/admin/assay-catalog" element={withAdminPermission(<PublicAssayCatalogPage />, "catalog:view")} />
            <Route path="/admin/subpanels" element={withAdminPermission(<SubpanelDefinitionsPage />, "assay.panel:view")} />
            <Route path="/admin/assay-groups" element={withAdminPermission(<AssayGroupsPage />, "assay.panel:view")} />
            <Route path="/admin/assay-subpanels" element={withAdminPermission(<AssaySubpanelsPage />, "assay.panel:view")} />
            <Route path="/admin/assay-setups" element={withRouteLoader(<AssaySetupPage />)} />
            <Route path="/admin/asp/create" element={withRouteLoader(<AssaySetupPage />)} />
            <Route path="/admin/asp/:id/view" element={withRouteLoader(<AssayEditorPage mode="view" />)} />
            <Route path="/admin/asp/:id/edit" element={withRouteLoader(<AssayEditorPage mode="edit" />)} />
            <Route path="/admin/asp" element={withRouteLoader(<AssaysPage />)} />
            <Route path="/admin/aspc/create" element={withRouteLoader(<AssayConfigurationEditorPage mode="create" />)} />
            <Route path="/admin/aspc/:id/view" element={withRouteLoader(<AssayConfigurationEditorPage mode="view" />)} />
            <Route path="/admin/aspc/:id/edit" element={withRouteLoader(<AssayConfigurationEditorPage mode="edit" />)} />
            <Route path="/admin/aspc" element={withRouteLoader(<AssayConfigurationsPage />)} />
            <Route path="/admin/genelists/create" element={withRouteLoader(<GeneListEditorPage mode="create" />)} />
            <Route path="/admin/genelists/:id/view" element={withRouteLoader(<GeneListEditorPage mode="view" />)} />
            <Route path="/admin/genelists/:id/edit" element={withRouteLoader(<GeneListEditorPage mode="edit" />)} />
            <Route path="/admin/genelists" element={withRouteLoader(<GeneListsPage />)} />
            <Route path="/admin/users/create" element={withRouteLoader(<UserEditorPage mode="create" />)} />
            <Route path="/admin/users/:id/view" element={withRouteLoader(<UserEditorPage mode="view" />)} />
            <Route path="/admin/users/:id/edit" element={withRouteLoader(<UserEditorPage mode="edit" />)} />
            <Route path="/admin/users" element={withRouteLoader(<UsersPage />)} />
            <Route path="/admin/roles/create" element={withRouteLoader(<RoleEditorPage mode="create" />)} />
            <Route path="/admin/roles/:id/view" element={withRouteLoader(<RoleEditorPage mode="view" />)} />
            <Route path="/admin/roles/:id/edit" element={withRouteLoader(<RoleEditorPage mode="edit" />)} />
            <Route path="/admin/roles" element={withRouteLoader(<RolesPage />)} />
            <Route path="/admin/permissions/create" element={withRouteLoader(<PermissionEditorPage mode="create" />)} />
            <Route path="/admin/permissions/:id/view" element={withRouteLoader(<PermissionEditorPage mode="view" />)} />
            <Route path="/admin/permissions/:id/edit" element={withRouteLoader(<PermissionEditorPage mode="edit" />)} />
            <Route path="/admin/permissions" element={withRouteLoader(<PermissionsPage />)} />
            <Route path="/admin/samples/create" element={withRouteLoader(<AdminSampleEditorPage mode="create" />)} />
            <Route path="/admin/samples/:id/view" element={withRouteLoader(<AdminSampleEditorPage mode="view" />)} />
            <Route path="/admin/samples/:id/edit" element={withRouteLoader(<AdminSampleEditorPage mode="edit" />)} />
            <Route path="/admin/samples" element={withRouteLoader(<AdminSamplesPage />)} />
            <Route path="/profile" element={withRouteLoader(<Profile />)} />
            <Route path="*" element={withRouteLoader(<NotFoundPage />)} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
