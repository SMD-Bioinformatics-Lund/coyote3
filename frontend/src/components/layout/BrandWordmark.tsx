import { cn } from "@/lib/utils"

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("brand-gradient-text text-2xl font-medium tracking-wider", className)}>
      COYOTE3
    </span>
  )
}
