import { Link } from "react-router-dom"

export function PermissionCategoryOverview({ rows, canEdit }: { rows: any[]; canEdit: boolean }) {
  if (!rows.length) return null
  const grouped = rows.reduce((acc, row) => {
    const category = String(row?.category || "Uncategorized")
    acc[category] = [...(acc[category] || []), row]
    return acc
  }, {} as Record<string, any[]>)
  return (
    <section className="glass-card p-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">Permission Categories</h2>
          <p className="text-sm text-muted-foreground">All loaded policies grouped by category for quick review.</p>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
          {rows.length} policies
        </span>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {(Object.entries(grouped) as Array<[string, any[]]>).map(([category, items]) => (
          <section key={category} className="rounded-lg border border-border bg-background/70 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide">{category}</h3>
              <span className="rounded-full bg-muted px-2 py-0.5 type-meta font-bold leading-5 text-muted-foreground">{items.length}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <Link
                  key={String(item.permission_id || item._id)}
                  to={`/admin/permissions/${encodeURIComponent(String(item.permission_id || item._id))}/${canEdit && !item.system_managed ? "edit" : "view"}`}
                  className="rounded-full border border-border bg-card px-2 py-1 text-xs font-semibold leading-4 text-foreground hover:border-primary/40 hover:text-primary"
                  title={item.description || item.label || item.permission_id}
                >
                  {item.permission_id}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  )
}
