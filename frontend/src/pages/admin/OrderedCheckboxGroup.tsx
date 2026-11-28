// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Button } from "@/components/ui/button"
import { ChoiceOption } from "@/components/ui/choice-group"
import { icon } from "@/lib/assets"
import { normalizeList, optionLabel, optionValue } from "./resource-list"
import type { FormField } from "./resource-specs"

/** Checked analyses form an ordered prefix. Other analyses retain their report order. */
export function OrderedCheckboxGroup({ options = [], value, onChange, disabled }: {
  options: FormField["options"]
  value: unknown
  onChange: (next: string[]) => void
  disabled?: boolean
}) {
  const selected = normalizeList(value)
  const labels = new Map(options.map(option => [optionValue(option), optionLabel(option)]))
  const remaining = [...labels.keys()].filter(key => !selected.includes(key))

  function move(from: number, to: number) {
    const next = [...selected]
    next[from] = selected[to]
    next[to] = selected[from]
    onChange(next)
  }

  if (disabled && !selected.length) {
    return <p className="type-body-sm text-muted-foreground">Default order</p>
  }
  return <ul className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
    {(disabled ? selected : [...selected, ...remaining]).map((key, index) => {
      const checked = index < selected.length
      const label = labels.get(key) || key
      return <li key={key} className={checked ? (disabled ? "flex items-center gap-1" : "flex w-full items-center gap-1 border-b border-border") : undefined}>
        {checked && <span className="shrink-0 type-meta tabular-nums text-muted-foreground">{index + 1}.</span>}
        <ChoiceOption inline option={{ value: key, label }} checked={checked} disabled={disabled}
          onCheckedChange={enabled => onChange(enabled ? [...selected, key] : selected.filter(item => item !== key))} />
        {checked && !disabled && <div className="ml-auto flex">
          <Button type="button" size="icon-sm" variant="ghost" aria-label={`Move ${label} up`} disabled={index === 0} onClick={() => move(index, index - 1)}><icon.arrowUp /></Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label={`Move ${label} down`} disabled={index === selected.length - 1} onClick={() => move(index, index + 1)}><icon.arrowDown /></Button>
        </div>}
      </li>
    })}
  </ul>
}
