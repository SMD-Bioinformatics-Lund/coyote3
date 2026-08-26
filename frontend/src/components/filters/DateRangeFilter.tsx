import { CalendarDays } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { DATE_RANGE_OPTIONS, parseDateRangePreset, type DateRangePreset } from "./date-range"

type DateRangeFilterProps = {
  preset: DateRangePreset
  from: string
  until: string
  onPresetChange: (preset: DateRangePreset) => void
  onFromChange: (value: string) => void
  onUntilChange: (value: string) => void
  onApply: () => void
  idPrefix?: string
  label?: string
}

export function DateRangeFilter({
  preset,
  from,
  until,
  onPresetChange,
  onFromChange,
  onUntilChange,
  onApply,
  idPrefix = "date-range",
  label = "Date added",
}: DateRangeFilterProps) {
  const invalid = Boolean(from && until && from > until)
  const presetId = `${idPrefix}-preset`
  const fromId = `${idPrefix}-from`
  const untilId = `${idPrefix}-until`

  return (
    <>
      <div className="space-y-1">
        <label htmlFor={presetId} className="block text-[11px] font-semibold text-muted-foreground">{label}</label>
        <div className="relative">
          <CalendarDays className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <select
            id={presetId}
            className="paper-inset h-9 min-w-[165px] rounded-lg pl-9 pr-8 text-sm font-medium"
            value={preset}
            onChange={(event) => onPresetChange(parseDateRangePreset(event.target.value))}
          >
            {DATE_RANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
      </div>
      {preset === "custom" && (
        <>
          <div className="space-y-1">
            <label htmlFor={fromId} className="block text-[11px] font-semibold text-muted-foreground">From</label>
            <Input
              id={fromId}
              type="date"
              className="h-9 w-[155px]"
              value={from}
              onChange={(event) => onFromChange(event.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor={untilId} className="block text-[11px] font-semibold text-muted-foreground">Until</label>
            <Input
              id={untilId}
              type="date"
              className="h-9 w-[155px]"
              value={until}
              onChange={(event) => onUntilChange(event.target.value)}
              aria-invalid={invalid || undefined}
            />
          </div>
          <Button type="button" variant="secondary" className="h-9" disabled={invalid} onClick={onApply}>
            Apply dates
          </Button>
          {invalid && (
            <p className="w-full text-xs font-medium text-destructive" role="alert">
              The From date must be before or equal to the Until date.
            </p>
          )}
        </>
      )}
    </>
  )
}
