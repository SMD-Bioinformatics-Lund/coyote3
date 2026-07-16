import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { api } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FileText, Activity, ArrowRight, Dna, Search as SearchIcon } from "lucide-react"
import { Input } from "@/components/ui/input"
import { PageShell } from "@/components/layout/PageShell"
import { fullDateTime, humanRelativeDate, shortCount } from "@/lib/detail-formatters"
import { sampleReported, sampleSubpanel } from "@/lib/sample-shape"

function countBadges(sample: any) {
  const counts = sample?.data_counts || {}
  return [
    counts.snvs !== undefined ? { label: "SNV", value: shortCount(counts.snvs), className: "border-primary/30 bg-primary/10 text-primary" } : null,
    counts.cnvs !== undefined ? { label: "CNV", value: shortCount(counts.cnvs), className: "border-tier3/30 bg-tier3/10 text-tier3" } : null,
    counts.fusions !== undefined ? { label: "Fusion", value: shortCount(counts.fusions), className: "border-rna/30 bg-rna/10 text-rna" } : null,
    counts.translocations !== undefined ? { label: "SV", value: shortCount(counts.translocations), className: "border-tier2/30 bg-tier2/10 text-tier2" } : null,
    counts.cov ? { label: "Cov", value: "yes", className: "border-pass/30 bg-pass/10 text-pass" } : null,
  ].filter(Boolean)
}

export function Samples() {
  const [searchParams, setSearchParams] = useSearchParams()
  
  // Extract filters from URL
  const category = searchParams.get("panel_type") || searchParams.get("category")
  const assay = searchParams.get("assay")
  const panelTech = searchParams.get("panel_tech")
  const group = searchParams.get("assay_group") || searchParams.get("group")
  const profileScope = searchParams.get("profile_scope") === "all" ? "all" : "production"
  const searchStr = searchParams.get("search_str") || ""

  const [searchInput, setSearchInput] = useState(searchStr)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['samples', category, panelTech, assay, group, profileScope, searchStr],
    queryFn: () => {
      const params = new URLSearchParams()
      if (category) params.set("panel_type", category)
      if (panelTech) params.set("panel_tech", panelTech)
      if (assay) params.set("assay", assay)
      if (group) params.set("assay_group", group)
      params.set("profile_scope", profileScope)
      if (searchStr) params.set("search_str", searchStr)
      
      return api.get(`/samples?${params.toString()}`).then(res => res.data)
    }
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <Activity className="h-8 w-8 animate-spin" />
          <p>Loading samples...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-destructive/10 text-destructive border-l-4 border-destructive p-4 rounded">
          <p className="font-bold">Failed to load samples</p>
          <p>{error instanceof Error ? error.message : "Unknown error"}</p>
        </div>
      </div>
    )
  }

  const samples = data?.live_samples || []
  const showAllProfiles = profileScope === "all"
  const setProfileScope = (nextScope: "production" | "all") => {
    const newParams = new URLSearchParams(searchParams)
    if (nextScope === "all") newParams.set("profile_scope", "all")
    else newParams.delete("profile_scope")
    setSearchParams(newParams)
  }

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <PageShell
        eyebrow="Cases"
        title="Samples"
        description="Manage and analyze loaded genomic cases."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className="inline-flex rounded-xl border border-border bg-card/70 p-1 shadow-sm">
              <button
                type="button"
                onClick={() => setProfileScope("production")}
                className={`rounded-lg px-3 py-1.5 text-xs font-black uppercase tracking-wider transition-colors ${!showAllProfiles ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              >
                Production
              </button>
              <button
                type="button"
                onClick={() => setProfileScope("all")}
                className={`rounded-lg px-3 py-1.5 text-xs font-black uppercase tracking-wider transition-colors ${showAllProfiles ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              >
                All profiles
              </button>
            </div>
            <form 
              onSubmit={(e) => {
                e.preventDefault()
                const newParams = new URLSearchParams(searchParams)
                if (searchInput) newParams.set("search_str", searchInput)
                else newParams.delete("search_str")
                setSearchParams(newParams)
              }}
              className="flex items-center space-x-2 relative"
            >
              <div className="relative">
                <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input 
                  type="text" 
                  placeholder="Search by Case ID..." 
                  className="w-[250px] rounded-xl border-border bg-card pl-9 shadow-sm focus-visible:ring-primary lg:w-[350px]"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
              </div>
              <Button type="submit" className="rounded-xl shadow-md">Search</Button>
            </form>
          </div>
        }
      >

        {/* Filters Summary */}
        {(category || assay || group || searchStr || showAllProfiles) && (
          <div className="glass-card flex items-center gap-2 text-sm text-muted-foreground px-5 py-3">
            <span className="font-bold uppercase tracking-wider text-xs mr-2">Active Filters</span>
            <Badge variant="secondary" className="uppercase bg-primary/10 text-primary hover:bg-primary/20 rounded-md">{showAllProfiles ? "all profiles" : "production"}</Badge>
            {searchStr && <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 rounded-md">Search: {searchStr}</Badge>}
            {category && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{category}</Badge>}
            {panelTech && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{panelTech}</Badge>}
            {assay && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{assay}</Badge>}
            {group && <Badge variant="secondary" className="uppercase bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-md shadow-sm">{group}</Badge>}
            <Link to="/samples" className="text-xs font-bold text-destructive hover:underline ml-auto bg-destructive/10 px-3 py-1 rounded-md" onClick={() => setSearchInput("")}>Clear All</Link>
          </div>
        )}

        <div className="glass-card overflow-hidden border-border/50">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-separate border-spacing-0">
              <thead className="bg-muted text-foreground font-black uppercase tracking-wider text-[11px] border-b-2 border-border shadow-sm dark:bg-muted/70">
                <tr>
                  <th className="border-b-2 border-r border-border px-3 py-2">Sample</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Case ID</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Case Clarity</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Control</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Control Clarity</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Profile</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Assay</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Subpanel</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Analysis</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Report</th>
                  <th className="border-b-2 border-r border-border px-3 py-2">Counts</th>
                  <th className="border-b-2 border-r border-border px-3 py-2 text-right">Added</th>
                  <th className="border-b-2 border-border px-3 py-2 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {samples.length === 0 ? (
                  <tr>
                    <td colSpan={13} className="px-4 py-12 text-center text-muted-foreground">
                      <Dna className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
                      <p>No samples found.</p>
                    </td>
                  </tr>
                ) : (
                  samples.map((sample: any) => (
                    <tr key={sample._id} className="hover:bg-primary/5 transition-colors border-b border-border/20 last:border-0 group">
                      <td className="border-r border-border/55 px-3 py-2 font-bold text-primary">
                        <Link to={`/samples/${sample._id}`} className="hover:underline flex items-center gap-2">
                          <div className="bg-primary/10 p-1.5 rounded-lg text-primary shadow-sm transition-colors duration-100 group-hover:bg-primary/15">
                            <FileText className="h-4 w-4" />
                          </div>
                          {sample.name || sample.case_id}
                        </Link>
                      </td>
                      <td className="border-r border-border/55 px-3 py-2 font-semibold">{sample.case_id || sample.case?.id || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2 text-muted-foreground">{sample.case?.clarity_id || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2 font-semibold">{sample.control_id || sample.control?.id || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2 text-muted-foreground">{sample.control?.clarity_id || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2">
                        <Badge variant="outline" className="border-validation/30 bg-validation/10 font-bold uppercase text-validation">
                          {sample.profile || "-"}
                        </Badge>
                      </td>
                      <td className="border-r border-border/55 px-3 py-2 font-semibold">{sample.assay || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2 text-muted-foreground font-medium">{sampleSubpanel(sample) || "-"}</td>
                      <td className="border-r border-border/55 px-3 py-2">
                        <Badge 
                          className={
                            sample.ingest_status === "ready" 
                              ? "border-pass/30 bg-pass/15 text-pass hover:bg-pass/20 font-bold" 
                              : "border-warn/30 bg-warn/15 text-warn hover:bg-warn/20 font-bold"
                          }
                        >
                          {sample.ingest_status}
                        </Badge>
                      </td>
                      <td className="border-r border-border/55 px-3 py-2">
                        <Badge
                          variant="outline"
                          className={sampleReported(sample) ? "border-primary/30 bg-primary/10 text-primary font-bold" : "border-warn/30 bg-warn/10 text-warn font-bold"}
                        >
                          {sampleReported(sample) ? "reported" : "unreported"}
                        </Badge>
                      </td>
                      <td className="border-r border-border/55 px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {countBadges(sample).length ? countBadges(sample).map((item: any) => (
                            <Badge key={item.label} variant="outline" className={`${item.className} font-bold`}>
                              {item.label} {item.value}
                            </Badge>
                          )) : <span className="text-muted-foreground">-</span>}
                        </div>
                      </td>
                      <td
                        className="border-r border-border/55 px-3 py-2 text-right text-muted-foreground font-medium whitespace-nowrap"
                        title={fullDateTime(sample.time_added)}
                      >
                        {humanRelativeDate(sample.time_added)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <Link to={`/samples/${sample._id}`}>
                          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-xl hover:bg-primary hover:text-primary-foreground shadow-sm">
                            <ArrowRight className="h-4 w-4" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {samples.length > 0 && (
            <div className="border-t border-border/50 p-4 flex items-center justify-between text-xs font-semibold text-muted-foreground bg-muted/20">
              <div>
                Showing <span className="text-foreground">1</span> to <span className="text-foreground">{samples.length}</span> of <span className="text-foreground">{samples.length}</span> results
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled className="rounded-lg font-bold">Previous</Button>
                <Button variant="outline" size="sm" disabled className="rounded-lg font-bold">Next</Button>
              </div>
            </div>
          )}
        </div>
      </PageShell>
    </div>
  )
}
