import { cn } from "@/lib/utils"

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("text-2xl font-medium tracking-wider", className)}>
      COYOT3
    </span>
  )
}
