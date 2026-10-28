import { Select as SelectPrimitive } from "@base-ui/react/select"
import { icon } from "@/lib/assets"

export function Select({ label, value, options, disabled, onValueChange }: {
  label: string
  value: string
  options: { value: string; label: string }[]
  disabled?: boolean
  onValueChange: (value: string) => void
}) {
  return <SelectPrimitive.Root value={value} items={options} disabled={disabled} onValueChange={next => onValueChange(next || "")}>
    <SelectPrimitive.Trigger aria-label={label} className="form-control flex w-full min-w-0 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left type-body disabled:opacity-60">
      <SelectPrimitive.Value className="min-w-0 break-words" />
      <SelectPrimitive.Icon><icon.chevronDown className="size-4 shrink-0" /></SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner sideOffset={6} alignItemWithTrigger={false} className="z-50">
        <SelectPrimitive.Popup className="max-h-80 w-[var(--anchor-width)] overflow-y-auto rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lg">
          <SelectPrimitive.List>
            {options.map(option => <SelectPrimitive.Item key={option.value} value={option.value} className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 type-body outline-none data-highlighted:bg-accent data-highlighted:text-accent-foreground">
              <span className="size-4 shrink-0"><SelectPrimitive.ItemIndicator><icon.check className="size-4" /></SelectPrimitive.ItemIndicator></span>
              <SelectPrimitive.ItemText className="min-w-0 break-words">{option.label}</SelectPrimitive.ItemText>
            </SelectPrimitive.Item>)}
          </SelectPrimitive.List>
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  </SelectPrimitive.Root>
}
