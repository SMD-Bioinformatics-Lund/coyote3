import { useState } from "react"

export function useAnnotationVisibility(table: "catalog" | "matrix") {
  const key = `coyote3:${table}:annotations`
  const [visible, setVisible] = useState(() => {
    try {
      const stored = localStorage.getItem(key)
      if (stored !== null) return stored === "true"
    } catch {
      // Storage may be unavailable in restricted browser sessions.
    }
    return table === "catalog"
  })
  const toggle = (
    <label className="inline-flex items-center gap-2 text-xs text-foreground">
      <input
        type="checkbox"
        className="table-checkbox accent-primary"
        checked={visible}
        onChange={(event) => {
          const next = event.target.checked
          setVisible(next)
          try {
            localStorage.setItem(key, String(next))
          } catch {
            // Keep the control usable without persistent browser storage.
          }
        }}
      />
      Annotations
    </label>
  )
  return { visible, toggle }
}
