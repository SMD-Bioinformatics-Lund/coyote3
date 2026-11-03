import { useState } from "react"
import { SearchInput } from "@/components/ui/search-input"
import { cn } from "@/lib/utils"

export interface Choice {
  value: string
  label: string
  description?: string
  ariaLabel?: string
  disabled?: boolean
}

/** Shared inset checkbox control for raised choice groups and admin forms. */
export function ChoiceOption({ option, checked, disabled, onCheckedChange }: {
  option: Choice
  checked: boolean
  disabled?: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <label className={cn("form-option flex min-w-0 gap-2.5 px-3 py-2", option.description ? "items-start" : "items-center")}>
      <input
        type="checkbox"
        className={cn("size-4 shrink-0 accent-primary", option.description && "mt-0.5")}
        aria-label={option.ariaLabel}
        checked={checked}
        disabled={disabled || option.disabled}
        onChange={event => onCheckedChange(event.target.checked)}
      />
      <span className="min-w-0 type-body-sm">
        <span className="block break-words font-medium text-foreground">{option.label}</span>
        {option.description && <span className="block break-words type-meta text-muted-foreground">{option.description}</span>}
      </span>
    </label>
  )
}

/** Raised selection group with shared headers, optional search and inset options. */
export function ChoiceGroup({ title, description, options, value, onValueChange, searchable = false, layout = "grid" }: {
  title: string
  description?: string
  options: Choice[]
  value: string[]
  onValueChange: (value: string[]) => void
  searchable?: boolean
  layout?: "grid" | "list" | "inline"
}) {
  const [search, setSearch] = useState("")
  const visible = options.filter(option =>
    `${option.label} ${option.value} ${option.description || ""}`
      .toLowerCase().includes(search.toLowerCase()),
  )
  return (
    <fieldset className="form-option-group min-w-0 rounded-xl p-3">
      <legend className="sr-only">{title}</legend>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="type-body-sm font-semibold">{title}</span>
        <span className="type-meta tabular-nums text-muted-foreground">{value.length} selected</span>
      </div>
      {description && <p className="mb-3 type-body-sm text-muted-foreground">{description}</p>}
      {searchable && <SearchInput aria-label={`Search ${title.toLowerCase()}`} placeholder="Search by name or ID…" value={search} onChange={event => setSearch(event.target.value)} className="mb-3 max-w-none" />}
      <div className={cn(
        "gap-2 p-1",
        layout === "inline" ? "flex flex-wrap" : "grid",
        layout === "grid" && "sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2",
        searchable && "max-h-52 overflow-y-auto overscroll-contain",
      )}>
        {visible.map(option => <ChoiceOption key={option.value} option={{ ...option, ariaLabel: option.ariaLabel || option.label }} checked={value.includes(option.value)} onCheckedChange={checked => onValueChange(checked ? [...value, option.value] : value.filter(item => item !== option.value))} />)}
        {!visible.length && <p className="col-span-full py-3 type-body-sm text-muted-foreground">{search ? "No matching options. Try another name or ID." : "No options available."}</p>}
      </div>
    </fieldset>
  )
}
