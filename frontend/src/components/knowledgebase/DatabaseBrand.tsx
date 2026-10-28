import { useState } from "react"
import { databaseLogo } from "@/lib/database-logos"
import { appPath } from "@/lib/runtime-paths"
import { cn } from "@/lib/utils"

/** Show a source logo once, retaining product qualifiers and a readable image-error fallback. */
export function DatabaseBrand({ source, label, className, logoClassName }: {
  source: string
  label: string
  className?: string
  logoClassName?: string
}) {
  const logo = databaseLogo(source)
  const src = logo ? appPath(logo.src) : null
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const showLogo = logo && src && failedSource !== src
  const name = logo?.alt.replace(/ logo$/i, "") || ""
  const qualifier = name && label.toLowerCase().startsWith(name.toLowerCase())
    ? label.slice(name.length).replace(/^[\s·:–\u2014-]+/, "") : label

  return <span className={cn("inline-flex min-w-0 items-center gap-2", className)} title={label}>
    {showLogo ? <>
      <img src={src} alt={logo.alt} onError={() => setFailedSource(src)}
        className={cn("h-6 w-16 shrink-0 object-contain", logoClassName)} />
      {qualifier && <span>{qualifier}</span>}
    </> : <span>{label}</span>}
  </span>
}
