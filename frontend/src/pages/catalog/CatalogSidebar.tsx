import { familyLabels, matchesCatalogCategory, type Offering } from "./offering-types"
import { icon } from "@/lib/assets"

const categories = [
  { modality: "dna", label: "DNA", methods: [["wgs", "WGS"], ["panel-dna", "Panels"]] },
  { modality: "rna", label: "RNA", methods: [["wts", "WTS"], ["panel-rna", "Panels"]] },
] as const

/** Browse modality, family, biological group and diagnosis using published offerings. */
export function CatalogSidebar({ offerings, selected, group, diagnosis, expanded,
  onExpandedChange, onSelect }: {
  offerings: Offering[]; selected: string; group: string; diagnosis: string
  expanded: ReadonlySet<string>; onExpandedChange: (keys: Set<string>) => void
  onSelect: (category: string, group: string, diagnosis: string) => void
}) {
  const branchKey = (value: string, groupId = "") => groupId ? JSON.stringify([value, groupId]) : value
  const row = (value: string, label: string, accessibleLabel = label,
    groupId = "", diagnosisId = "", expandable = false) => {
    const active = selected === value && group === groupId && diagnosis === diagnosisId
    const ancestor = !active && selected !== "all" && !diagnosisId && (
      value === selected.split(":")[0] || selected === value && (!groupId || groupId === group)
    )
    const level = diagnosisId ? "diagnosis" : groupId ? "group" : value.includes(":") ? "family" : "modality"
    const typography = level === "modality" ? "type-body font-semibold"
      : level === "family" ? "type-body-sm" : level === "group" ? "type-meta" : "type-label normal-case"
    const key = branchKey(value, groupId)
    const open = expanded.has(key)
    const count = offerings.filter(item => matchesCatalogCategory(item, value)
      && (!groupId || item.group_id === groupId)
      && (!diagnosisId || item.diagnosis_id === diagnosisId)).length
    return <div className="flex min-w-0 items-center gap-0.5">
      {expandable && <button type="button" aria-label={`${open ? "Collapse" : "Expand"} ${accessibleLabel}`}
        aria-expanded={open}
        className="flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
        onClick={() => {
          const next = new Set(expanded)
          if (open) next.delete(key)
          else next.add(key)
          onExpandedChange(next)
        }}>
        <icon.chevronRight aria-hidden="true" className={`size-3 ${open ? "rotate-90" : ""}`} />
      </button>}
      <button type="button" aria-label={accessibleLabel} aria-pressed={active}
      data-modality={value.split(":")[0]} data-level={level} data-ancestor={ancestor || undefined}
      className={`catalog-sidebar-option flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-ring ${typography}`}
      onClick={() => {
        if (value !== "all") {
          const next = new Set(expanded)
          next.add(value.split(":")[0])
          if (value.includes(":")) next.add(value)
          if (groupId) next.add(branchKey(value, groupId))
          onExpandedChange(next)
        }
        onSelect(value, groupId, diagnosisId)
      }}>
      <span className="flex min-w-0 items-center gap-1">
        {value === "all" && <icon.layers className="mr-1 size-4 shrink-0" aria-hidden="true" />}
        {value === "dna" && <icon.dna className="mr-1 size-4 shrink-0" aria-hidden="true" />}
        {value === "rna" && <icon.flaskConical className="mr-1 size-4 shrink-0" aria-hidden="true" />}
        <span className="min-w-0 break-words">{label}</span>
      </span>
      <span className="catalog-sidebar-count shrink-0 type-meta type-numeric">{count}</span>
      </button>
    </div>
  }
  return <aside className="surface-panel catalog-sidebar self-start">
    <div className="catalog-sidebar-heading flex items-center gap-2 px-4 py-3">
      <span className="rounded-lg border border-primary/20 bg-primary/10 p-1.5 text-primary shadow-sm">
        <icon.listFilter className="size-4" aria-hidden="true" />
      </span>
      <h2 className="type-section-title">Browse tests</h2>
    </div>
    <nav aria-label="Test categories" className="space-y-3 p-3">
      {row("all", "All tests")}
      {categories.map(category => {
        const methods = category.methods.map(([id, label]) => ({ id: String(id), label: String(label) }))
        const additional = [...new Set(offerings.filter(item => item.modality === category.modality)
          .map(item => item.family))].filter(id => !methods.some(method => method.id === id))
          .sort().map(id => ({ id, label: familyLabels[id] || id }))
        return <section key={category.modality} aria-label={`${category.label} tests`}>
        {row(category.modality, category.label, category.label, "", "", true)}
        {expanded.has(category.modality) && <div className="catalog-sidebar-branch ml-3 border-l pl-2">{[...methods, ...additional].map(({ id, label }) => {
          const key = `${category.modality}:${id}`
          const path = `${category.label} ${label}`
          const scoped = offerings.filter(item => matchesCatalogCategory(item, key))
          const groups = [...new Map(scoped.map(item => [item.group_id, item.group_label])).entries()]
            .sort((a, b) => a[1].localeCompare(b[1]))
          return <div key={id}>
            {row(key, label, path, "", "", true)}
            {expanded.has(key) && <div className="catalog-sidebar-branch ml-2 border-l pl-1">
              {groups.map(([groupId, groupLabel]) => <div key={groupId}>
                {row(key, groupLabel, `${path} / ${groupLabel}`, groupId, "", true)}
                {expanded.has(branchKey(key, groupId)) && <div className="catalog-sidebar-branch ml-2 border-l pl-1">
                  {[...new Map(scoped.filter(item => item.group_id === groupId)
                    .map(item => [item.diagnosis_id, item.diagnosis_label])).entries()]
                    .sort((a, b) => a[1].localeCompare(b[1]))
                    .map(([id, label]) => <div key={id}>
                      {row(key, label, `${path} / ${groupLabel} / ${label}`, groupId, id)}
                    </div>)}
                </div>}
              </div>)}
            </div>}
          </div>
        })}</div>}
      </section>})}
    </nav>
  </aside>
}
