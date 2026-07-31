import { type ReactNode } from "react"

import { cn } from "@/lib/utils"

type Segment<T extends string> = {
  value: T
  label: ReactNode
  disabled?: boolean
}

export function SegmentedControl<T extends string>({
  items,
  value,
  onValueChange,
  className,
  ariaLabel,
}: {
  items: readonly Segment<T>[]
  value: T
  onValueChange: (value: T) => void
  className?: string
  ariaLabel: string
}) {
  const activeIndex = Math.max(0, items.findIndex((item) => item.value === value))
  const indicatorStyle = {
    width: `calc((100% - 2px) / ${Math.max(items.length, 1)})`,
    transform: `translateX(${activeIndex * 100}%)`,
  }

  return (
    <div className={cn("segmented-control", className)} role="tablist" aria-label={ariaLabel}>
      <span aria-hidden="true" className="segmented-control-indicator" style={indicatorStyle} />
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={item.value === value}
          data-segmented-control-item
          disabled={item.disabled}
          onClick={() => onValueChange(item.value)}
          className={cn("segmented-control-item", item.value === value && "is-active")}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
