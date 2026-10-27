import { FileCheck2, Upload } from "lucide-react"
import { useRef, useState, type ComponentProps } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type Props = Omit<ComponentProps<"input">, "type" | "value" | "defaultValue" | "ref"> & {
  label: string
  hint?: string
}

export function FileUpload({ label, hint, className, disabled, onChange, multiple, ...props }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [names, setNames] = useState<string[]>([])
  const Icon = names.length ? FileCheck2 : Upload
  return <div className={cn("rounded-xl border border-border bg-background p-3 shadow-sm focus-within:ring-2 focus-within:ring-ring/35", disabled && "opacity-50", className)}>
    <input {...props} ref={input} type="file" multiple={multiple} aria-label={label} disabled={disabled} className="sr-only" onChange={event => {
      setNames(Array.from(event.target.files || [], file => file.name))
      onChange?.(event)
    }} />
    <div className="flex flex-wrap items-center gap-3">
      <span className="rounded-lg bg-primary/10 p-2 text-primary"><Icon aria-hidden="true" className="size-5" /></span>
      <div className="min-w-0 flex-1 basis-32">
        <p className="break-words type-body-sm font-medium" aria-live="polite">{names.length ? names.join(", ") : "No file selected"}</p>
        {hint && <p className="mt-1 type-meta text-muted-foreground">{hint}</p>}
      </div>
      <Button type="button" variant="outline" size="sm" disabled={disabled} aria-label={`Browse ${label}`} onClick={() => input.current?.click()}><Upload aria-hidden="true" />{names.length ? "Change file" : "Browse files"}</Button>
    </div>
  </div>
}
