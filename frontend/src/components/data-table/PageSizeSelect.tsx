import { TABLE_PAGE_SIZE_OPTIONS } from "@/lib/user-settings"
import { cn } from "@/lib/utils"

type PageSizeSelectProps = {
  value: number
  onValueChange: (value: number) => void
  id?: string
  disabled?: boolean
  showPageSuffix?: boolean
  optionLabel?: (value: number) => string
  className?: string
  ariaLabel?: string
}

export function PageSizeSelect({
  value,
  onValueChange,
  id,
  disabled = false,
  showPageSuffix = false,
  optionLabel,
  className,
  ariaLabel = "Rows per page",
}: PageSizeSelectProps) {
  return (
    <select
      id={id}
      aria-label={id ? undefined : ariaLabel}
      value={value}
      disabled={disabled}
      onChange={(event) => onValueChange(Number(event.target.value))}
      className={cn(
        "paper-inset rounded-lg px-2 py-1 text-xs font-semibold text-foreground outline-none focus:ring-3 focus:ring-ring/30 disabled:opacity-50",
        className,
      )}
    >
      {TABLE_PAGE_SIZE_OPTIONS.map((option) => (
        <option key={option} value={option}>
          {optionLabel?.(option) ?? `${option}${showPageSuffix ? " / page" : ""}`}
        </option>
      ))}
    </select>
  )
}
