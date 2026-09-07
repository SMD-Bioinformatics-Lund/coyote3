import { ArrowRight } from "lucide-react"
import { Link, type LinkProps } from "react-router-dom"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { cn } from "@/lib/utils"

type DetailNavigationButtonProps = {
  to: LinkProps["to"]
  label: string
  description: string
  state?: LinkProps["state"]
  className?: string
}

export function DetailNavigationButton({
  to,
  label,
  description,
  state,
  className,
}: DetailNavigationButtonProps) {
  return (
    <AppTooltip context="Table action" label={label} content={description}>
      <Link
        to={to}
        state={state}
        aria-label={label}
        className={cn("detail-navigation-button", className)}
      >
        <ArrowRight aria-hidden="true" className="size-4" />
      </Link>
    </AppTooltip>
  )
}
