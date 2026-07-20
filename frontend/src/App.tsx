import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Suspense, lazy, type ReactNode } from "react"
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AppLoader } from "./components/layout/AppLoader"
import { Layout } from "./components/layout/Layout"
import { notify } from "./components/notifications/notification-store"
import { APP_BASENAME } from "./lib/runtime-paths"
import { Login } from "./pages/Login"

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })))
const Samples = lazy(() => import("./pages/Samples").then((module) => ({ default: module.Samples })))
const SampleDetail = lazy(() => import("./pages/SampleDetail").then((module) => ({ default: module.SampleDetail })))
const VariantDetail = lazy(() => import("./pages/VariantDetail").then((module) => ({ default: module.VariantDetail })))
const CNVDetail = lazy(() => import("./pages/CNVDetail").then((module) => ({ default: module.CNVDetail })))
const FusionDetail = lazy(() => import("./pages/FusionDetail").then((module) => ({ default: module.FusionDetail })))
const TranslocationDetail = lazy(() => import("./pages/TranslocationDetail").then((module) => ({ default: module.TranslocationDetail })))
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
const AboutPage = lazy(() => import("./pages/StaticPages").then((module) => ({ default: module.AboutPage })))
const NotFoundPage = lazy(() => import("./pages/StaticPages").then((module) => ({ default: module.NotFoundPage })))
const CoverageBlacklistPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.CoverageBlacklistPage })))
const GeneInfoPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.GeneInfoPage })))
const PublicAspGenesPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.PublicAspGenesPage })))
const PublicGenelistPage = lazy(() => import("./pages/CommonResourcePages").then((module) => ({ default: module.PublicGenelistPage })))
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })))
const SavedReportPage = lazy(() => import("./pages/SavedReportPage").then((module) => ({ default: module.SavedReportPage })))
const NotificationHistoryPage = lazy(() => import("./pages/NotificationHistoryPage").then((module) => ({ default: module.NotificationHistoryPage })))
const UiRouteAuditPage = lazy(() => import("./pages/admin/UiRouteAuditPage").then((module) => ({ default: module.UiRouteAuditPage })))

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

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={APP_BASENAME || undefined}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={withRouteLoader(<ForgotPassword />)} />
          <Route path="/reset-password" element={withRouteLoader(<ResetPassword />)} />
          <Route element={<Layout />}>
            <Route path="/" element={withRouteLoader(<Dashboard />)} />
            <Route path="/samples" element={withRouteLoader(<Samples />)} />
            <Route path="/samples/:id" element={withRouteLoader(<SampleDetail />)} />
            <Route path="/samples/:id/variant/:varId" element={withRouteLoader(<VariantDetail />)} />
            <Route path="/samples/:id/cnv/:varId" element={withRouteLoader(<CNVDetail />)} />
            <Route path="/samples/:id/fusion/:varId" element={withRouteLoader(<FusionDetail />)} />
            <Route path="/samples/:id/translocation/:varId" element={withRouteLoader(<TranslocationDetail />)} />
            <Route path="/samples/:id/reports/:reportId" element={withRouteLoader(<SavedReportPage />)} />
            <Route path="/variants" element={withRouteLoader(<TieredVariantSearch />)} />
            <Route path="/variants/search" element={withRouteLoader(<TieredVariantSearch />)} />
            <Route path="/variants/reported/:variantId/:tier" element={withRouteLoader(<TieredVariantContext />)} />
            <Route path="/reports" element={withRouteLoader(<ReportsPage />)} />
            <Route path="/notifications" element={withRouteLoader(<NotificationHistoryPage />)} />
            <Route path="/about" element={withRouteLoader(<AboutPage />)} />
            <Route path="/contact" element={withRouteLoader(<ContactPage />)} />
            <Route path="/public" element={withRouteLoader(<PublicCatalog />)} />
            <Route path="/public/catalog" element={withRouteLoader(<PublicCatalog />)} />
            <Route path="/public/matrix" element={withRouteLoader(<PublicCatalogMatrix />)} />
            <Route path="/public/genelists/:genelistId/view" element={withRouteLoader(<PublicGenelistPage />)} />
            <Route path="/public/asp/:aspId/genes" element={withRouteLoader(<PublicAspGenesPage />)} />
            <Route path="/public/gene/:geneId/info" element={withRouteLoader(<GeneInfoPage />)} />
            <Route path="/coverage/blacklisted/:group" element={withRouteLoader(<CoverageBlacklistPage />)} />
            <Route path="/admin" element={withRouteLoader(<AdminHub />)} />
            <Route path="/admin/audit" element={withRouteLoader(<AdminAuditPage />)} />
            <Route path="/admin/controls" element={withRouteLoader(<AdminControlsPage />)} />
            <Route path="/admin/ingest" element={withRouteLoader(<AdminIngestPage />)} />
            <Route path="/admin/schemas" element={withRouteLoader(<AdminSchemasPage />)} />
            <Route path="/admin/ui-routes" element={withRouteLoader(<UiRouteAuditPage />)} />
            <Route path="/admin/:resource/create" element={withRouteLoader(<AdminResourceEditorPage mode="create" />)} />
            <Route path="/admin/:resource/:id/view" element={withRouteLoader(<AdminResourceEditorPage mode="view" />)} />
            <Route path="/admin/:resource/:id/edit" element={withRouteLoader(<AdminResourceEditorPage mode="edit" />)} />
            <Route path="/admin/:resource" element={withRouteLoader(<AdminResourcePage />)} />
            <Route path="/profile" element={withRouteLoader(<Profile />)} />
            <Route path="*" element={withRouteLoader(<NotFoundPage />)} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
