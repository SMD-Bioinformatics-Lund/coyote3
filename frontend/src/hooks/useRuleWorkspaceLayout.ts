import { useState } from "react"

function storedWidth(label: string, fallback: number) {
  if (typeof window === "undefined") return fallback
  try {
    const value = Number(window.localStorage.getItem(`clinical-rules-width:${label}`))
    return Number.isFinite(value) && value > 0 ? value : fallback
  } catch {
    return fallback
  }
}

/** Keep clinical and query workspace layout state separate from rule authoring state. */
export function useRuleWorkspaceLayout(kind: "clinical" | "query") {
  const [listCollapsed, setListCollapsed] = useState(false)
  const [sectionsCollapsed, setSectionsCollapsed] = useState(false)
  const [listWidth, setListWidth] = useState(() => kind === "query"
    ? Math.min(440, Math.max(210, storedWidth("Resize query-rule list", 300)))
    : storedWidth("Resize rule-set list", 272))
  const [sectionsWidth, setSectionsWidth] = useState(() => storedWidth("Resize report sections", 208))
  const [previewWidth, setPreviewWidth] = useState(() => kind === "query"
    ? Math.min(600, Math.max(280, storedWidth("Resize query preview", 340)))
    : storedWidth("Resize text preview", 380))

  return { listCollapsed, setListCollapsed, sectionsCollapsed, setSectionsCollapsed,
    listWidth, setListWidth, sectionsWidth, setSectionsWidth, previewWidth, setPreviewWidth }
}
