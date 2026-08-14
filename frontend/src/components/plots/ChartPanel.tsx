import { Download, FileDown, ImageDown } from "lucide-react"
import { useRef, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import {
  type ChartDataRow,
  exportChartAsPng,
  exportChartAsSvg,
  exportRowsAsCsv,
} from "@/lib/chart-export"

export function ChartPanel({
  title,
  description,
  filename,
  data,
  children,
}: {
  title: string
  description?: string
  filename: string
  data: ChartDataRow[]
  children: ReactNode
}) {
  const chartRef = useRef<HTMLDivElement>(null)
  const safeName = filename.replace(/[^a-z0-9_.-]+/gi, "_").replace(/^_+|_+$/g, "")

  return (
    <section className="chart-panel flex h-full min-h-0 flex-col overflow-hidden rounded-lg p-2.5">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-foreground">{title}</h3>
          {description && <p className="mt-0.5 text-[11px] text-muted-foreground">{description}</p>}
        </div>
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="xs" title="Export chart PNG" onClick={() => exportChartAsPng(chartRef.current, `${safeName}.png`)}>
            <ImageDown className="h-3.5 w-3.5" />
            PNG
          </Button>
          <Button type="button" variant="outline" size="xs" title="Export chart SVG" onClick={() => exportChartAsSvg(chartRef.current, `${safeName}.svg`)}>
            <Download className="h-3.5 w-3.5" />
            SVG
          </Button>
          <Button type="button" variant="outline" size="xs" title="Export chart data CSV" onClick={() => exportRowsAsCsv(data, `${safeName}.csv`)}>
            <FileDown className="h-3.5 w-3.5" />
            CSV
          </Button>
        </div>
      </div>
      <div ref={chartRef} className="min-h-0 flex-1">
        {children}
      </div>
    </section>
  )
}
