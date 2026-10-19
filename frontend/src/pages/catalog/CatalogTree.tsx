import type { Category } from "@/pages/admin/catalog-types"
import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"

/** Render parent-linked catalog entries without putting analysis controls in navigation. */
export function CatalogTree({ categories, selected, onSelect, parent = null, ancestors = [] }: {
  categories: Record<string, Category>
  selected?: string
  onSelect: (key: string) => void
  parent?: string | null
  ancestors?: string[]
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const containsSelection = (key: string) => {
    const seen = new Set<string>()
    let current = selected
    while (current && !seen.has(current)) {
      if (current === key) return true
      seen.add(current)
      current = categories[current]?.parent_key || undefined
    }
    return false
  }
  return <ul className="space-y-1">
    {Object.entries(categories).filter(([, node]) => (node.parent_key || null) === parent)
      .filter(([key]) => !ancestors.includes(key)).map(([key, node]) => {
        const hasChildren = Object.values(categories).some((child) => child.parent_key === key)
        const open = expanded[key] ?? containsSelection(key)
        const label = node.label || node.title || key
        return <li key={key}>
        <div className="flex items-center gap-1">
          {hasChildren ? <button type="button" aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
            aria-expanded={open} className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
            onClick={() => setExpanded((current) => ({ ...current, [key]: !open }))}>
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button> : <span className="w-6 shrink-0" />}
        <button type="button" aria-current={selected === key ? "page" : undefined}
          className={`block w-full rounded-md px-2 py-1.5 text-left hover:bg-muted ${ancestors.length === 0 ? "type-body font-semibold" : ancestors.length === 1 ? "type-body-sm font-semibold" : "type-meta"} ${selected === key ? "bg-primary/10 font-semibold text-primary" : "text-foreground"}`}
          onClick={() => { setExpanded((current) => ({ ...current, [key]: true })); onSelect(key) }}>{label}</button>
        </div>
        {hasChildren && open && <div className="ml-3 border-l border-border pl-2">
          <CatalogTree categories={categories} selected={selected} onSelect={onSelect}
            parent={key} ancestors={[...ancestors, key]} />
        </div>}
      </li>})}
  </ul>
}
