import type { ReactNode } from "react"
import { ArrowDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { QueryCondition } from "./query-condition-types"
import { QueryConditionSummary } from "./QueryConditionSummary"

type Exception = { id: string; mode: string; condition?: QueryCondition; [key: string]: unknown }
type Layer = {
  source: string; version: number | null; fields?: string[]; application?: string
  name?: string
  scope?: { assay_group: string | null; asp_id: string | null; diagnosis_id: string | null; family?: string | null; environment?: string | null }
  content?: { evidence_mode: string | null; exceptions: Exception[] | null; exception_mode?: string }
  population_frequency_fields?: string[]
  superseded_by_preview?: boolean
}
export type PolicyResolution = {
  scope?: { analysis: string; intent: string }
  evidence_mode: string | null; exceptions: Exception[]; lineage: Layer[]
  requires_sample_context?: boolean
  compiled_conditions?: { id: string; mode: string; predicate: unknown }[]
}
const label = (value: string) => value.replaceAll("_", " ")
const sourceName = (row: Layer) => row.source === "default" ? "Application defaults"
  : row.source === "preview" ? "Selected version" : row.name || row.source
const sameBranch = (a: Layer, b: Layer) => a.application === b.application

function RuleDetail({ rule }: { rule: Exception }) {
  return <div className="min-w-0 space-y-2 rounded-lg border border-border bg-background/60 p-3">
    <div className="flex flex-wrap items-center gap-2"><strong className="break-all type-label">{rule.id}</strong><Badge variant="outline">{label(rule.mode)}</Badge></div>
    {rule.condition && <QueryConditionSummary condition={rule.condition} />}
    <dl className="space-y-1 type-supporting">{Object.entries(rule).filter(([key]) => !["id", "mode", "condition"].includes(key)).map(([key, item]) => <div key={key}>
      <dt className="font-medium">{label(key)}</dt><dd className="break-words">{Array.isArray(item) ? item.join(", ") : typeof item === "object" ? JSON.stringify(item) : String(item)}</dd>
    </div>)}</dl>
  </div>
}

function Branch({ title, operator, children }: { title: string; operator?: string; children: ReactNode }) {
  return <section className="min-w-0 space-y-2 rounded-xl border border-border bg-background/40 p-3" aria-label={title}>
    <h4 className="flex flex-wrap items-center gap-2 type-label">{operator && <Badge variant="outline">{operator}</Badge>}{title}</h4>
    <div className="space-y-2 border-l-2 border-primary/25 pl-3 type-supporting">{children}</div>
  </section>
}

function Inheritance({ value }: { value: PolicyResolution }) {
  return <details className="rounded-xl border border-border p-3">
    <summary className="cursor-pointer type-label">Sources and overridden rules</summary>
    <p className="my-2 type-supporting text-muted-foreground">Read top to bottom. Replaced settings remain visible here; only the final flow below is applied.</p>
    <ol className="space-y-3">{value.lineage.map((row, index) => {
      const later = value.lineage.slice(index + 1).filter(next => sameBranch(row, next) && !next.superseded_by_preview)
      const replacement = row.superseded_by_preview ? later.find(next => next.source === "preview") : undefined
      const modeReplacement = replacement ?? later.find(next => next.content?.evidence_mode != null)
      const exceptionReplacement = replacement ?? later.find(next => next.content?.exceptions != null && next.content.exception_mode !== "extend")
      return <li key={index} className="min-w-0 space-y-2">
        {index > 0 && <ArrowDown aria-hidden="true" className="mx-auto h-4 w-4 text-muted-foreground" />}
        <div className="space-y-2 rounded-lg border border-border bg-background/50 p-3">
          <h4 className="break-all type-label">{sourceName(row)}{row.version != null && ` · v${row.version}`}</h4>
          {row.scope && <p className="break-words type-supporting text-muted-foreground">{[
            row.scope.assay_group ? `Group: ${row.scope.assay_group}` : "All groups",
            row.scope.asp_id ? `Assay: ${row.scope.asp_id}` : "All assays",
            row.scope.diagnosis_id ? `Diagnosis: ${row.scope.diagnosis_id}` : "All diagnoses",
            row.scope.family, row.scope.environment,
          ].filter(Boolean).join(" · ")}</p>}
          {row.superseded_by_preview && <p className="type-supporting">Published version replaced in this preview. Inherited settings come from its ancestors.</p>}
          {row.application === "somatic_snv_exceptions" && <p className="type-supporting">Germline exception branch; does not replace somatic evidence.</p>}
          {!row.content ? <p className="type-supporting text-muted-foreground">{row.fields?.map(label).join(", ") || "Inherited settings"}</p> : <>
            {row.content.evidence_mode != null && row.application !== "somatic_snv_exceptions" && <div className="type-supporting">
              <span className={modeReplacement ? "line-through text-muted-foreground" : "font-medium"}>Evidence: {label(row.content.evidence_mode)}</span>
              <p>{modeReplacement ? `Replaced by ${sourceName(modeReplacement)}` : "Active evidence setting"}</p>
            </div>}
            {row.content.evidence_mode === null && row.application !== "somatic_snv_exceptions" && <p className="type-supporting text-muted-foreground">Evidence: inherit previous setting</p>}
            {row.content.exceptions === null ? <p className="type-supporting text-muted-foreground">Exceptions: inherit previous list</p> : <>
              <p className="type-supporting">{row.content.exception_mode === "extend" ? "Add to inherited exceptions" : "Replace inherited exceptions"} · {row.content.exceptions.length} rule(s)</p>
              {exceptionReplacement && <p className="type-label">Exceptions replaced by {sourceName(exceptionReplacement)}</p>}
              {row.content.exceptions.map(rule => <details key={rule.id} className="rounded-lg border border-border p-2">
                <summary className="cursor-pointer break-words type-supporting"><span className={exceptionReplacement ? "line-through text-muted-foreground" : ""}>{rule.id}</span> · {exceptionReplacement ? "Overridden" : "Active"}</summary>
                <div className="mt-2"><RuleDetail rule={rule} /></div>
              </details>)}
            </>}
          </>}
        </div>
      </li>
    })}</ol>
  </details>
}

/** Display query composition and provenance without evaluating findings in the browser. */
export function QueryPolicyFlow({ value, analysis }: { value: PolicyResolution; analysis: string }) {
  const admissions = value.exceptions.filter(rule => rule.mode === "admit")
  const consequences = value.exceptions.filter(rule => rule.mode === "extend_consequence")
  const exclusions = value.exceptions.filter(rule => rule.mode === "exclude")
  const frequencyFields = value.lineage.find(row => row.source === "default" && !row.application)?.population_frequency_fields ?? []
  const rules = (items: Exception[]) => items.map(rule => <RuleDetail key={rule.id} rule={rule} />)
  const baseline = analysis === "snv" ? <Branch title="Ordinary evidence" operator="AND">
    <p>One genotype: AF ≥ sample.filters.min_freq and ≤ sample.filters.max_freq; DP ≥ sample.filters.min_depth; VD ≥ sample.filters.min_alt_reads.{value.evidence_mode === "paired" ? " Genotype type must be case." : " A genotype role label is not required."}</p>
    {value.evidence_mode === "paired" && <Branch title="Control evidence" operator="OR"><p>Control AF ≤ sample.filters.max_control_freq and DP ≥ sample.filters.min_depth.</p><p>No control genotype exists.</p></Branch>}
    <Branch title="Population frequencies" operator="AND"><p>Each configured numeric frequency must be ≤ sample.filters.max_popfreq. Missing, null and string values pass this check.</p>{frequencyFields.map(field => <p key={field} className="break-all font-mono">{field}</p>)}</Branch>
    <Branch title="Eligible consequences" operator="OR"><p>consequence_terms matches the VEP consequences selected in the sample filters.</p>{rules(consequences)}</Branch>
  </Branch> : analysis === "cnv" ? <Branch title="Ordinary CNV selection" operator="AND">
    <p>Normal-control calls are excluded unless the sample/assay configuration includes them.</p>
    <Branch title="Copy-number evidence" operator="OR">
      <p>ratio &lt; sample.filters.cnv_loss_cutoff or ratio &gt; sample.filters.cnv_gain_cutoff, AND (sample.filters.min_cnv_size &lt; size &lt; sample.filters.max_cnv_size OR ratio &gt; 3).</p>
      <p>Missing/null ratio AND nonempty SR or PR evidence.</p>
    </Branch>
    <p>Match the effective CNV gene scope. A restricted empty gene scope matches no findings.</p>
  </Branch> : analysis === "fusion" ? <Branch title="Ordinary fusion selection" operator="AND">
    <p>Match the effective fusion gene scope. A restricted empty gene scope matches no findings.</p>
    <p>A single calls element must meet the selected effect, caller and description filters, plus minimum spanning reads/pairs. Arriba does not require spanning pairs when callers are selected. Unselected filters add no restriction.</p>
  </Branch> : <p>Match the effective translocation gene scope. A restricted empty scope matches no findings. These checks run after repository selection.</p>
  return <div className="min-w-0 space-y-4">
    <p className="type-supporting">Application defaults included · {value.lineage.length} source layer(s) · {value.exceptions.length} active exception(s){value.evidence_mode ? ` · ${label(value.evidence_mode)} evidence` : ""}</p>
    <Inheritance value={value} />
    <ArrowDown aria-hidden="true" className="mx-auto h-5 w-5 text-primary" />
    <section aria-label="Final selection flow" className="min-w-0 space-y-3">
      <h3 className="type-section-title">Final selection flow</h3>
      <p className="type-supporting text-muted-foreground">Application rules and active policy conditions combined. sample.filters values come from the sample and its recorded assay configuration.</p>
      <Branch title="Keep a finding only when all required gates pass" operator="AND">
        <Branch title="Sample boundary"><p>Finding belongs to the authorized sample. Policy exceptions cannot bypass sample identity or access checks.</p></Branch>
        {analysis === "snv" && <Branch title="Gene and position scope" operator="AND"><p>Use verification positions when configured; otherwise use the effective SNV gene scope. A restricted empty scope matches no findings. Apply selected false-positive and irrelevant-status filters.</p></Branch>}
        {analysis === "snv" && value.evidence_mode === "exception_only" ? <Branch title="Admission exceptions only" operator="OR">{admissions.length ? rules(admissions) : <p>No admission exceptions: no findings can pass.</p>}</Branch> : <Branch title="Evidence or an admission exception" operator="OR">{baseline}{rules(admissions)}</Branch>}
        <Branch title="Exclude matching exceptions" operator="NOT / OR">{exclusions.length ? rules(exclusions) : <p>No exclusion exceptions.</p>}</Branch>
        {analysis === "snv" && <Branch title="Excluded flags"><p>Reject FILTER values selected in sample.filters.exclude_flags, including findings admitted by an exception. An empty exclusion list adds no restriction.</p></Branch>}
        {analysis === "cnv" && <Branch title="After query selection"><p>Apply the selected CNV effects to the retrieved findings.</p></Branch>}
      </Branch>
      {value.lineage.some(row => row.application === "somatic_snv_exceptions") && <p className="type-supporting">Published germline exceptions are included in the somatic flow with a germline__ ID prefix. Somatic evidence remains active.</p>}
      {value.requires_sample_context && <p className="type-supporting">Conditions containing sample.filters references are shown symbolically until a sample is selected in Test rules.</p>}
      <p className="type-supporting text-muted-foreground">Save this version and open Test rules for the complete MongoDB predicate, resolved values, post-filters and finding counts for an authorized sample.</p>
    </section>
  </div>
}
