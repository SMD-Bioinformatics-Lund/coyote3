import { igvDataPath } from "@/lib/external-links"
import { cn } from "@/lib/utils"

type IgvSettings = { base_folder?: string; bam_subfolder?: string; design_bed?: string }

function pathError(value: string, required: boolean) {
  value = value.trim()
  if (!value) return required ? "Base folder is required." : ""
  return value.startsWith("/") || value.split("/").some((part) => ["", ".", ".."].includes(part))
    || /[\\:%?#,"']/.test(value) || [...value].some((char) => char.charCodeAt(0) < 32)
    ? "Use a relative path without traversal, URLs, or drive letters." : ""
}

export function AssayIgvFields({ value, onChange, disabled }: {
  value: IgvSettings | null
  onChange: (value: IgvSettings | null) => void
  disabled?: boolean
}) {
  const settings = value || {}
  const enabled = Object.values(settings).some(Boolean)
  const fields = [
    ["base_folder", "Base folder"],
    ["bam_subfolder", "BAM subfolder"],
    ["design_bed", "Design BED"],
  ] as const
  const valid = enabled && fields.every(([key]) => !pathError(settings[key] || "", key === "base_folder"))
  return <div className="space-y-3">
    <div className="grid gap-3 md:grid-cols-3">
      {fields.map(([key, label]) => {
        const error = pathError(settings[key] || "", enabled && key === "base_folder")
        return <label key={key} className="min-w-0 space-y-1">
          <span className="type-label">{label}</span>
          {error && <span className="block type-meta text-destructive">{error}</span>}
          <input aria-label={label} aria-invalid={Boolean(error)} disabled={disabled}
            value={settings[key] || ""}
            onChange={(event) => {
              const next = { ...settings, [key]: event.target.value }
              onChange(Object.values(next).some(Boolean) ? next : null)
            }}
            className={cn("w-full rounded border bg-background px-2 py-1.5 type-body-sm", error ? "border-destructive" : "border-input")}
          />
        </label>
      })}
    </div>
    {valid && <dl className="space-y-1 break-all type-meta">
      <dt className="font-semibold">BAM path preview</dt>
      <dd>{igvDataPath([settings.base_folder?.trim(), settings.bam_subfolder?.trim(), "case.bam"].filter(Boolean).join("/"))}</dd>
      {settings.design_bed && <>
        <dt className="font-semibold">Design BED path</dt>
        <dd>{igvDataPath(`${settings.base_folder?.trim()}/${settings.design_bed.trim()}`)}</dd>
      </>}
    </dl>}
  </div>
}
