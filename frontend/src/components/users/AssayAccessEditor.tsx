export type AssayGrant = { asp_id: string; environments: string[] }

export function AssayAccessEditor({ value, onChange, options = [], environments, disabled }: {
  value: AssayGrant[]
  onChange: (next: AssayGrant[]) => void
  options?: { value: string; label?: string; group?: string }[]
  environments: string[]
  disabled?: boolean
}) {
  const grants = Array.isArray(value) ? value : []
  const choices = [...options]
  for (const row of grants) {
    if (!choices.some(choice => choice.value === row.asp_id)) {
      choices.push({ value: row.asp_id, label: `${row.asp_id} (existing assignment)` })
    }
  }
  function toggle(assay: string, environment: string, checked: boolean) {
    const selected = new Set(grants.find(row => row.asp_id === assay)?.environments || [])
    if (checked) selected.add(environment)
    else selected.delete(environment)
    const next = grants.filter(row => row.asp_id !== assay)
    if (selected.size) next.push({ asp_id: assay, environments: environments.filter(env => selected.has(env)) })
    onChange(next.sort((a, b) => a.asp_id.localeCompare(b.asp_id)))
  }
  return <div className="overflow-x-auto rounded-lg border border-border">
    <table className="w-full border-collapse text-sm">
      <thead className="bg-muted"><tr><th className="p-2 text-left">Assay</th>
        {environments.map(environment => <th key={environment} className="p-2 text-center capitalize">{environment}</th>)}
      </tr></thead>
      <tbody>{choices.map(assay => <tr key={assay.value} className="border-t border-border">
        <th scope="row" className="p-2 text-left font-medium">{assay.label || assay.value}<span className="block type-meta text-muted-foreground">{assay.value}</span></th>
        {environments.map(environment => <td key={environment} className="p-2 text-center">
          <input type="checkbox" disabled={disabled} aria-label={`${assay.value} ${environment}`}
            checked={grants.some(row => row.asp_id === assay.value && row.environments.includes(environment))}
            onChange={event => toggle(assay.value, environment, event.target.checked)} />
        </td>)}
      </tr>)}</tbody>
    </table>
    {!choices.length && <p className="p-3 type-body-sm text-muted-foreground">No registered assays available.</p>}
  </div>
}
