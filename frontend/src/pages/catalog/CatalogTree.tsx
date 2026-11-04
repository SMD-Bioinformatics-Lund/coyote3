import type { Category } from "@/pages/admin/catalog-types"
import { icon } from "@/lib/assets"
import { useEffect, useState } from "react"
import { valueBadgeClass } from "@/lib/badge-colors"
import { Button } from "@/components/ui/button"

export type CatalogTreeAppearance = Record<string, {
  level: "modality" | "family" | "group" | "diagnosis"; tone?: string
}>

/** Render parent-linked entries with separate expand, select and optional add actions. */
export function CatalogTree({ categories, selected, onSelect, parent = null, ancestors = [], defaultExpanded = [], appearances, onAdd }: {
  categories: Record<string, Category>
  selected?: string
  onSelect: (key: string) => void
  parent?: string | null
  ancestors?: string[]
  defaultExpanded?: readonly string[]
  appearances?: CatalogTreeAppearance
  onAdd?: (key: string) => void
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(defaultExpanded.map(key => [key, true])))
  const selectionPath = new Set<string>()
  let current = selected
  while (current && !selectionPath.has(current)) {
    selectionPath.add(current)
    current = categories[current]?.parent_key || undefined
  }
  const selectedPath = JSON.stringify([...selectionPath])
  useEffect(() => {
    const path: string[] = JSON.parse(selectedPath)
    setExpanded(previous => path.every(key => previous[key]) ? previous
      : { ...previous, ...Object.fromEntries(path.map(key => [key, true])) })
  }, [selectedPath])
  const containsSelection = (key: string) => selectionPath.has(key)
  return <ul className="space-y-1">
    {Object.entries(categories).filter(([, node]) => (node.parent_key || null) === parent)
      .filter(([key]) => !ancestors.includes(key)).map(([key, node]) => {
        const hasChildren = Boolean(onAdd) || Object.values(categories).some((child) => child.parent_key === key)
        const open = expanded[key] ?? containsSelection(key)
        const label = node.label || node.title || key
        const level = appearances?.[key]?.level || (["modality", "family", "group", "diagnosis"] as const)[Math.min(ancestors.length, 3)]
        const typography = level === "modality" ? "type-card-title" : level === "family"
          ? "type-body font-semibold" : level === "group" ? "type-body-sm font-semibold" : "type-meta"
        const active = selected === key
        return <li key={key}>
        <div className="flex items-center gap-1">
          {hasChildren ? <button type="button" aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
            aria-expanded={open} className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
            onClick={() => setExpanded((current) => ({ ...current, [key]: !open }))}>
            {open ? <icon.chevronDown className="h-4 w-4" /> : <icon.chevronRight className="h-4 w-4" />}
          </button> : <span className="w-6 shrink-0" />}
        <button type="button" aria-current={active ? "page" : undefined}
          data-level={level} data-ancestor={!active && containsSelection(key) || undefined}
          className={`catalog-tree-node block min-w-0 w-full rounded-lg px-2 py-1.5 text-left ${typography} ${appearances?.[key]?.tone ? valueBadgeClass(appearances[key].tone!) : ""}`}
          onClick={() => { setExpanded((current) => ({ ...current, [key]: true })); onSelect(key) }}>{label}</button>
        </div>
        {hasChildren && open && <div className="ml-3 border-l border-border pl-2">
          <CatalogTree categories={categories} selected={selected} onSelect={onSelect}
            parent={key} ancestors={[...ancestors, key]} appearances={appearances} onAdd={onAdd} />
          {onAdd && <Button variant="ghost" size="sm" className="mt-1 h-auto min-h-7 max-w-full whitespace-normal py-1 text-left text-primary"
            aria-label={`Add new entry under ${label}`} onClick={() => onAdd(key)}><icon.plus /> Add new entry</Button>}
        </div>}
      </li>})}
  </ul>
}
