import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Suspense, lazy } from "react"
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Layout } from "./components/layout/Layout"
import { notify } from "./components/notifications/notification-store"

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })))
const Samples = lazy(() => import("./pages/Samples").then((module) => ({ default: module.Samples })))
const SampleDetail = lazy(() => import("./pages/SampleDetail").then((module) => ({ default: module.SampleDetail })))
const VariantDetail = lazy(() => import("./pages/VariantDetail").then((module) => ({ default: module.VariantDetail })))
const CNVDetail = lazy(() => import("./pages/CNVDetail").then((module) => ({ default: module.CNVDetail })))
const FusionDetail = lazy(() => import("./pages/FusionDetail").then((module) => ({ default: module.FusionDetail })))
const TranslocationDetail = lazy(() => import("./pages/TranslocationDetail").then((module) => ({ default: module.TranslocationDetail })))
const Login = lazy(() => import("./pages/Login").then((module) => ({ default: module.Login })))
const ForgotPassword = lazy(() => import("./pages/AuthPasswordPages").then((module) => ({ default: module.ForgotPassword })))
const ResetPassword = lazy(() => import("./pages/AuthPasswordPages").then((module) => ({ default: module.ResetPassword })))
const AdminHub = lazy(() => import("./pages/AdminResourcePage").then((module) => ({ default: module.AdminHub })))
const AdminResourceEditorPage = lazy(() => import("./pages/AdminResourcePage").then((module) => ({ default: module.AdminResourceEditorPage })))
const AdminResourcePage = lazy(() => import("./pages/AdminResourcePage").then((module) => ({ default: module.AdminResourcePage })))
const AdminAuditPage = lazy(() => import("./pages/AdminUtilityPages").then((module) => ({ default: module.AdminAuditPage })))
const AdminControlsPage = lazy(() => import("./pages/AdminUtilityPages").then((module) => ({ default: module.AdminControlsPage })))
const AdminIngestPage = lazy(() => import("./pages/AdminUtilityPages").then((module) => ({ default: module.AdminIngestPage })))
const AdminSchemasPage = lazy(() => import("./pages/AdminUtilityPages").then((module) => ({ default: module.AdminSchemasPage })))
const PublicCatalog = lazy(() => import("./pages/PublicCatalog").then((module) => ({ default: module.PublicCatalog })))
const PublicCatalogMatrix = lazy(() => import("./pages/PublicCatalog").then((module) => ({ default: module.PublicCatalogMatrix })))
const TieredVariantContext = lazy(() => import("./pages/TieredVariantContext").then((module) => ({ default: module.TieredVariantContext })))
const TieredVariantSearch = lazy(() => import("./pages/TieredVariantSearch").then((module) => ({ default: module.TieredVariantSearch })))
const Profile = lazy(() => import("./pages/Profile").then((module) => ({ default: module.Profile })))
const ContactPage = lazy(() => import("./pages/StaticPages").then((module) => ({ default: module.ContactPage })))
const NotFoundPage = lazy(() => import("./pages/StaticPages").then((module) => ({ default: module.NotFoundPage })))
const StaticDocPage = lazy(() => import("./pages/StaticPages").then((module) => ({ default: module.StaticDocPage })))
const CoverageBlacklistPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.CoverageBlacklistPage })))
const GeneInfoPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.GeneInfoPage })))
const PublicAspGenesPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.PublicAspGenesPage })))
const PublicGenelistPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.PublicGenelistPage })))
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })))
const SavedReportPage = lazy(() => import("./pages/SavedReportPage").then((module) => ({ default: module.SavedReportPage })))
const NotificationHistoryPage = lazy(() => import("./pages/NotificationHistoryPage").then((module) => ({ default: module.NotificationHistoryPage })))
const UiRouteAuditPage = lazy(() => import("./pages/admin/UiRouteAuditPage").then((module) => ({ default: module.UiRouteAuditPage })))

const queryClient = new QueryClient({
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
  return (
    <div className="flex min-h-32 items-center justify-center p-6 text-sm font-semibold text-muted-foreground">
      Loading...
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/samples" element={<Samples />} />
              <Route path="/samples/:id" element={<SampleDetail />} />
              <Route path="/samples/:id/variant/:varId" element={<VariantDetail />} />
              <Route path="/samples/:id/cnv/:varId" element={<CNVDetail />} />
              <Route path="/samples/:id/fusion/:varId" element={<FusionDetail />} />
              <Route path="/samples/:id/translocation/:varId" element={<TranslocationDetail />} />
              <Route path="/samples/:id/reports/:reportId" element={<SavedReportPage />} />
              <Route path="/variants" element={<TieredVariantSearch />} />
              <Route path="/variants/search" element={<TieredVariantSearch />} />
              <Route path="/variants/reported/:variantId/:tier" element={<TieredVariantContext />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/notifications" element={<NotificationHistoryPage />} />
              <Route path="/catalog" element={<PublicCatalog />} />
              <Route path="/matrix" element={<PublicCatalogMatrix />} />
              <Route path="/contact" element={<ContactPage />} />
              <Route path="/docs/about" element={<StaticDocPage kind="about" />} />
              <Route path="/docs/changelog" element={<StaticDocPage kind="changelog" />} />
              <Route path="/docs/license" element={<StaticDocPage kind="license" />} />
              <Route path="/gene/:geneId" element={<GeneInfoPage />} />
              <Route path="/public/gene/:geneId/info" element={<GeneInfoPage />} />
              <Route path="/genelists/:genelistId/view" element={<PublicGenelistPage />} />
              <Route path="/asp/:aspId/genes" element={<PublicAspGenesPage />} />
              <Route path="/coverage/blacklisted/:group" element={<CoverageBlacklistPage />} />
              <Route path="/admin" element={<AdminHub />} />
              <Route path="/admin/audit" element={<AdminAuditPage />} />
              <Route path="/admin/controls" element={<AdminControlsPage />} />
              <Route path="/admin/ingest" element={<AdminIngestPage />} />
              <Route path="/admin/schemas" element={<AdminSchemasPage />} />
              <Route path="/admin/ui-routes" element={<UiRouteAuditPage />} />
              <Route path="/admin/:resource/create" element={<AdminResourceEditorPage mode="create" />} />
              <Route path="/admin/:resource/:id/view" element={<AdminResourceEditorPage mode="view" />} />
              <Route path="/admin/:resource/:id/edit" element={<AdminResourceEditorPage mode="edit" />} />
              <Route path="/admin/:resource" element={<AdminResourcePage />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
