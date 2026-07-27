import { useState, useRef, useEffect, useMemo } from "react"
import { Outlet, Link, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { useIsFetching, useQuery } from "@tanstack/react-query"
import { ThemeToggle } from "./theme-toggle"
import { Bell, BookOpen, Bug, FileQuestion, LayoutDashboard, Dna, Database, FileText, LifeBuoy, Settings, User, ChevronDown, LogOut, Search, PanelLeftClose, PanelRightClose, Lightbulb } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { apiPath, appPath } from "@/lib/runtime-paths"
import { runtimeConfig } from "@/lib/runtime-config"
import { useNotifications } from "@/components/notifications/use-notifications"
import { GlobalLoadingIndicator } from "@/components/layout/AppLoader"

type PublicContactPayload = {
  support?: Record<string, string>
  codebase?: Record<string, string>
  links?: Array<Record<string, string>>
}

export function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const isPublicRoute =
    location.pathname === "/about" ||
    location.pathname === "/contact" ||
    location.pathname === "/public" ||
    location.pathname.startsWith("/public/")
  const [isCollapsed, setIsCollapsed] = useState(true)
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const [activeAssayCategory, setActiveAssayCategory] = useState<string | null>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const assayMenuRef = useRef<HTMLDivElement>(null)
  const { appVersion } = runtimeConfig
  const { unreadCount } = useNotifications()
  const backgroundFetches = useIsFetching({
    predicate: (query) => query.state.data !== undefined,
  })

  const { data: user } = useQuery({
    queryKey: ['whoami'],
    queryFn: async () => {
      if (!isPublicRoute) return api.get('/auth/whoami').then(res => res.data)
      const response = await fetch(apiPath('/auth/whoami'), { credentials: "same-origin" })
      if (response.status === 401 || response.status === 403) return null
      if (!response.ok) return null
      return response.json()
    },
  })

  const { data: catalogData } = useQuery({
    queryKey: ['assay-catalog-nav'],
    queryFn: () => api.get('/public/assay-catalog/context').then(res => res.data),
    staleTime: 5 * 60 * 1000,
  })

  const { data: contactData } = useQuery({
    queryKey: ["public-contact"],
    queryFn: () => api.get<PublicContactPayload>("/public/contact").then(res => res.data),
    staleTime: 10 * 60 * 1000,
  })

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false)
      }
      if (assayMenuRef.current && !assayMenuRef.current.contains(event.target as Node)) {
        setActiveAssayCategory(null)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleLogout = async () => {
    try {
      await api.delete('/auth/sessions/current')
      navigate('/login')
    } catch (e) {
      console.error('Logout failed', e)
    }
  }

  const isAdmin = user?.role === 'superuser' || user?.role === 'admin'
  const publicOnlyMode = isPublicRoute && !user

  const navigationSections = useMemo(() => {
    if (publicOnlyMode) {
      return [
        {
          label: "Public",
          items: [
            { name: "Public Home", href: "/public", icon: BookOpen },
            { name: "Catalog", href: "/public/catalog", icon: FileText },
            { name: "Matrix", href: "/public/matrix", icon: Database },
            { name: "About", href: "/about", icon: FileQuestion },
            { name: "Contact", href: "/contact", icon: LifeBuoy },
          ],
        },
      ]
    }
    const sections = [
      {
        label: "Workspace",
        items: [
          { name: "Home", href: "/", icon: LayoutDashboard },
          { name: "Samples", href: "/samples", icon: Dna },
          { name: "Variant Search", href: "/variants/search", icon: Search },
          { name: "Reports", href: "/reports", icon: FileText },
        ],
      },
      {
        label: "Reference",
        items: [
          { name: "Matrix", href: "/public/matrix", icon: Database },
          { name: "Catalog", href: "/public/catalog", icon: FileText },
          { name: "About", href: "/about", icon: BookOpen },
          { name: "Contact", href: "/contact", icon: LifeBuoy },
        ],
      },
    ]
    if (isAdmin) {
      sections.push({
        label: "Administration",
        items: [{ name: "Admin Settings", href: "/admin", icon: Settings }],
      })
    }
    return sections
  }, [isAdmin, publicOnlyMode])

  const activeCategory = searchParams.get("panel_type") || searchParams.get("category") || ""
  const activePanelTech = searchParams.get("panel_tech") || ""
  const activeAssayGroup = searchParams.get("assay_group") || searchParams.get("group") || ""

  const navGroups = useMemo(() => {
    const groups = (catalogData?.meta?.nav_groups || catalogData?.nav_groups || []) as any[]
    return groups.filter((group) => group?.category && group?.family && group?.assay_group)
  }, [catalogData])

  const issueMenuLinks = useMemo(() => {
    const codebase = contactData?.codebase || {}
    return [
      {
        label: "Report a Bug",
        url: codebase.bug_report_url,
        icon: Bug,
      },
      {
        label: "Request a Feature",
        url: codebase.feature_request_url,
        icon: Lightbulb,
      },
      {
        label: "Support",
        url: codebase.support_request_url,
        icon: LifeBuoy,
      },
    ].filter((link) => Boolean(link.url))
  }, [contactData])

  const assayTree = useMemo(() => {
    const tree: Record<string, Record<string, any[]>> = {}
    for (const group of navGroups) {
      const category = String(group.category || "").toLowerCase()
      const family = String(group.family || "assay").toLowerCase()
      tree[category] ||= {}
      tree[category][family] ||= []
      tree[category][family].push(group)
    }
    for (const category of Object.keys(tree)) {
      for (const family of Object.keys(tree[category])) {
        tree[category][family].sort((a, b) => String(a.assay_group).localeCompare(String(b.assay_group)))
      }
    }
    return tree
  }, [navGroups])

  const assayCategories = useMemo(() => {
    const preferred = ["dna", "rna"]
    return [
      ...preferred.filter((category) => assayTree[category]),
      ...Object.keys(assayTree).filter((category) => !preferred.includes(category)).sort(),
    ]
  }, [assayTree])

  const setSampleGroupFilter = (group: any) => {
    const newParams = new URLSearchParams(searchParams)
    const isActive =
      activeCategory === group.category &&
      activePanelTech === group.family &&
      activeAssayGroup === group.assay_group
    for (const key of ["category", "panel_type", "panel_tech", "group", "assay_group", "assay"]) {
      newParams.delete(key)
    }
    if (!isActive) {
      newParams.set("panel_type", group.category)
      newParams.set("panel_tech", group.family)
      newParams.set("assay_group", group.assay_group)
    }
    setSearchParams(newParams)
    setActiveAssayCategory(null)
    if (location.pathname !== "/samples") navigate(`/samples?${newParams.toString()}`)
  }

  return (
    <div className="flex h-screen flex-col bg-background font-sans antialiased overflow-hidden">
      {backgroundFetches > 0 && <GlobalLoadingIndicator />}
      <div className="app-chrome-bg absolute inset-0 -z-10" />
      <header className="z-30 h-16 flex-shrink-0 border-b-2 border-primary/70 bg-card/95 shadow-sm">
        <div className="flex h-full w-full items-center justify-between gap-4 px-4">
          <Link to="/" className="flex shrink-0 items-center gap-3">
            <div className="rounded-lg bg-card/75 p-1 ">
              <img src={appPath("/logo.png")} alt="Coyote3" className="h-7 w-10 shrink-0 dark:invert" />
            </div>
            <div className="hidden sm:flex flex-col leading-tight">
              <span className="brand-gradient-text text-lg font-black tracking-wider">COYOT3</span>
            </div>
          </Link>

          {!publicOnlyMode && (
          <div className="relative flex h-full min-w-0 items-center" ref={assayMenuRef}>
            <div className="flex h-full items-center gap-1.5 py-2 text-xs font-bold text-foreground/80">
              {assayCategories.map(category => (
                <button
                  key={category}
                  onClick={() => setActiveAssayCategory(activeAssayCategory === category ? null : category)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-4 py-1.5 uppercase tracking-wider transition-colors duration-100",
                    activeCategory === category || activeAssayCategory === category
                      ? "bg-primary text-primary-foreground shadow-md"
                      : "hover:bg-muted/80"
                  )}
                >
                  {category}
                  <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-100", activeAssayCategory === category && "rotate-180")} />
                </button>
              ))}
            </div>
            {activeAssayCategory && (
              <div className="absolute left-0 top-full z-50 mt-2 w-[min(720px,calc(100vw-2rem))] rounded-xl border border-border bg-card p-3 shadow-lg">
                <div className="mb-3 flex items-center justify-between gap-3 border-b border-border pb-2">
                  <div>
                    <p className="text-[11px] font-black uppercase tracking-wider text-primary">{activeAssayCategory}</p>
                    <p className="text-xs text-muted-foreground">Filter samples by assay family and assay group.</p>
                  </div>
                  <Link
                    to="/samples"
                    onClick={() => setActiveAssayCategory(null)}
                    className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-bold hover:bg-muted"
                  >
                    All production
                  </Link>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {Object.entries(assayTree[activeAssayCategory] || {}).map(([family, groups]) => (
                    <div key={family} className="rounded-lg border border-border bg-background/70 p-2">
                      <h3 className="mb-2 rounded-md bg-muted/70 px-2 py-1 text-[11px] font-black uppercase tracking-wider text-foreground">
                        {family}
                      </h3>
                      <div className="space-y-1">
                        {groups.map(group => {
                          const isActive =
                            activeCategory === group.category &&
                            activePanelTech === group.family &&
                            activeAssayGroup === group.assay_group
                          return (
                            <button
                              key={`${group.category}-${group.family}-${group.assay_group}`}
                              type="button"
                              onClick={() => setSampleGroupFilter(group)}
                              className={cn(
                                "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs font-bold transition-colors",
                                isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                              )}
                              title={`${group.category.toUpperCase()} / ${group.family} / ${group.assay_group}`}
                            >
                              <span className="truncate">{String(group.assay_group).replaceAll("_", " ")}</span>
                              <span className={cn("rounded-full px-1.5 py-0.5 text-[10px]", isActive ? "bg-primary-foreground/20" : "bg-muted")}>
                                {(group.assays || []).length}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          )}

          <div className="ml-auto flex h-full items-center gap-2">
            {!publicOnlyMode && (
              <Link
                to="/notifications"
                className={cn(
                  "relative inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background/70 text-muted-foreground shadow-sm transition-colors hover:bg-muted hover:text-foreground",
                  location.pathname.startsWith("/notifications") && "bg-primary/10 text-primary"
                )}
                title="Notifications"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-primary px-1.5 py-0.5 text-center text-[10px] font-black leading-none text-primary-foreground shadow-sm">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                )}
              </Link>
            )}
            {publicOnlyMode ? (
              <Link
                to="/login"
                className="inline-flex h-10 items-center rounded-xl border border-border bg-background/70 px-3 text-sm font-bold text-primary shadow-sm transition-colors hover:bg-muted"
              >
                Sign in
              </Link>
            ) : (
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                className="flex items-center gap-2 rounded-xl border border-border bg-background/70 px-2 py-1.5 shadow-sm transition-colors hover:bg-muted"
              >
                <div className="brand-gradient-fill flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-bold text-primary-foreground shadow-md">
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="hidden sm:flex flex-col items-start text-xs leading-tight">
                  <span className="font-bold">{user?.username || "Loading..."}</span>
                  <span className="text-muted-foreground">{user?.role || "Guest"}</span>
                </div>
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </button>

              {isUserMenuOpen && (
                <div className="absolute right-0 top-full z-50 mt-2 w-60 rounded-xl border border-border bg-card py-1 shadow-lg">
              <Link to="/profile" className="flex items-center px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted/80" onClick={() => setIsUserMenuOpen(false)}>
                    <User className="mr-3 h-4 w-4 text-primary" /> Profile
                  </Link>
                  <Link to="/notifications" className="flex items-center justify-between px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted/80" onClick={() => setIsUserMenuOpen(false)}>
                    <span className="flex items-center">
                      <Bell className="mr-3 h-4 w-4 text-primary" /> Notifications
                    </span>
                    {unreadCount > 0 && (
                      <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-black text-primary-foreground">
                        {unreadCount}
                      </span>
                    )}
                  </Link>
                  <div className="my-1 border-t border-border/50"></div>
                  <Link to="/about" className="flex items-center px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted/80" onClick={() => setIsUserMenuOpen(false)}>
                    <FileQuestion className="mr-3 h-4 w-4 text-primary" /> About Coyote3
                  </Link>
                  <Link to="/contact" className="flex items-center px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted/80" onClick={() => setIsUserMenuOpen(false)}>
                    <LifeBuoy className="mr-3 h-4 w-4 text-primary" /> Contact
                  </Link>
                  {issueMenuLinks.map((link) => (
                    <a
                      key={link.label}
                      href={publicHref(link.url)}
                      target={isExternalHref(link.url) ? "_blank" : undefined}
                      rel={isExternalHref(link.url) ? "noreferrer" : undefined}
                      className="flex items-center px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted/80"
                      onClick={() => setIsUserMenuOpen(false)}
                    >
                      <link.icon className="mr-3 h-4 w-4 text-primary" /> {link.label}
                    </a>
                  ))}
                  <div className="my-1 border-t border-border/50"></div>
                  <button onClick={handleLogout} className="flex w-full items-center px-4 py-2.5 text-left text-sm font-medium text-destructive transition-colors hover:bg-destructive/10">
                    <LogOut className="mr-3 h-4 w-4" /> Logout
                  </button>
                </div>
              )}
            </div>
            )}
          </div>
        </div>
      </header>

      <div className="z-10 flex min-h-0 flex-1 overflow-hidden">
        <aside
          className={cn(
            "hidden md:flex flex-col flex-shrink-0 transition-[width] duration-150 ease-out border-r border-sidebar-border bg-sidebar/95 shadow-sm",
            isCollapsed ? "w-[52px]" : "w-[180px]"
          )}
        >
          <nav className="flex-1 overflow-y-auto px-1.5 py-3 overflow-x-hidden scrollbar-none">
            <div className="space-y-3">
              {navigationSections.map((section, sectionIndex) => (
                <div key={section.label} className="space-y-1">
                  {!isCollapsed ? (
                    <div className="px-2 pt-1 text-[10px] font-black uppercase tracking-wider text-muted-foreground/70">
                      {section.label}
                    </div>
                  ) : sectionIndex > 0 ? (
                    <div className="mx-auto h-px w-7 bg-sidebar-border" aria-hidden="true" />
                  ) : (
                    <div className="h-px" aria-hidden="true" />
                  )}
                  {section.items.map((item) => {
                    const isActive = location.pathname === item.href ||
                                    (item.href !== '/' && location.pathname.startsWith(item.href))
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        title={isCollapsed ? `${section.label}: ${item.name}` : undefined}
                        className={cn(
                          "group flex items-center rounded-lg py-2.5 text-sm font-semibold transition-colors duration-100",
                          isCollapsed ? "justify-center px-0" : "px-3",
                          isActive
                            ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20"
                            : "text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                        )}
                      >
                        <item.icon className={cn("h-5 w-5 flex-shrink-0", !isCollapsed && "mr-3")} />
                        {!isCollapsed && <span className="truncate">{item.name}</span>}
                      </Link>
                    )
                  })}
                </div>
              ))}
            </div>
          </nav>

          <div className="border-t border-sidebar-border p-2">
            <div className={cn("flex items-center gap-2", isCollapsed ? "flex-col justify-center" : "flex-col items-stretch")}>
              <div
                className={cn(
                  "text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70",
                  isCollapsed ? "max-w-8 text-center [writing-mode:vertical-rl]" : "px-2 pb-1"
                )}
                title={appVersion}
              >
                {appVersion}
              </div>
              <Button
                variant="ghost"
                size={isCollapsed ? "icon" : "sm"}
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={cn("text-muted-foreground hover:bg-muted/80 rounded-lg", !isCollapsed && "justify-start gap-2")}
                title="Toggle Sidebar"
              >
                {isCollapsed ? <PanelRightClose className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
                {!isCollapsed && <span>Collapse</span>}
              </Button>
              {!isCollapsed && (
                <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background/60 px-2 py-1">
                  <span className="text-xs font-semibold text-muted-foreground">Theme</span>
                  <ThemeToggle />
                </div>
              )}
              {isCollapsed && <ThemeToggle />}
            </div>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          <div className="w-full max-w-[2600px] px-4 py-3 2xl:px-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

function publicHref(url?: string) {
  if (!url) return "#"
  if (/^https?:\/\//i.test(url) || url.startsWith("mailto:") || url.startsWith("tel:")) return url
  return appPath(url)
}

function isExternalHref(url?: string) {
  return Boolean(url && /^https?:\/\//i.test(url))
}
