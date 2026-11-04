import { cn } from "@/lib/utils"

export function BrandWordmark({ className, variant = "gradient" }: {
  className?: string
  variant?: "gradient" | "chrome"
}) {
  return (
    <span className={cn(
      "text-2xl font-medium tracking-wider",
      variant === "chrome" ? "text-chrome-brand-foreground" : "brand-gradient-text",
      className,
    )}>
      COYOT3
    </span>
  )
}
