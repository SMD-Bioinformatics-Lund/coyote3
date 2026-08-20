import type { ReactNode } from "react"
import { LayoutGrid, Rows3 } from "lucide-react"

import { SegmentedControl } from "@/components/ui/segmented-control"
import {
  normalizeUserUiSettings,
  type AnalysisLayout,
  type SampleListLayout,
  type UserUiSettings,
} from "@/lib/user-settings"

const LAYOUT_ITEMS = [
  { value: "classic", label: "Classic" },
  { value: "modern", label: "Modern" },
] as const

export function UserUiSettingsControls({
  value,
  onChange,
  disabled = false,
}: {
  value: Partial<UserUiSettings> | null | undefined
  onChange: (settings: UserUiSettings) => void
  disabled?: boolean
}) {
  const settings = normalizeUserUiSettings(value)

  const updateAnalysisLayout = (layout: AnalysisLayout) => {
    if (disabled) return
    onChange({
      ...settings,
      analysis_layout: layout,
      analysis_modern_view_tried: settings.analysis_modern_view_tried || layout === "modern",
    })
  }

  const updateSampleListLayout = (layout: SampleListLayout) => {
    if (disabled) return
    onChange({
      ...settings,
      sample_list_layout: layout,
      sample_list_modern_view_tried: settings.sample_list_modern_view_tried || layout === "modern",
    })
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <SettingRow
        icon={LayoutGrid}
        title="Analysis workspace"
        description="Choose a combined findings page or separate analysis tabs."
      >
        <SegmentedControl
          ariaLabel="Analysis workspace layout"
          value={settings.analysis_layout}
          onValueChange={updateAnalysisLayout}
          items={LAYOUT_ITEMS.map((item) => ({ ...item, disabled }))}
          className="w-full sm:w-64"
        />
      </SettingRow>
      <SettingRow
        icon={Rows3}
        title="Samples worklist"
        description="Choose a combined worklist or separate live and reported tabs."
      >
        <SegmentedControl
          ariaLabel="Samples worklist layout"
          value={settings.sample_list_layout}
          onValueChange={updateSampleListLayout}
          items={LAYOUT_ITEMS.map((item) => ({ ...item, disabled }))}
          className="w-full sm:w-64"
        />
      </SettingRow>
    </div>
  )
}

function SettingRow({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof LayoutGrid
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-3 flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div>
          <h4 className="text-sm font-semibold text-foreground">{title}</h4>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </div>
  )
}
