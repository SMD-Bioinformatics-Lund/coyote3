export type Presentation = {
  label?: string | null
  title?: string | null
  description?: string | null
  subheading?: string
  input_material?: string[]
  sample_modes?: string[]
  analysis?: string[]
  tat?: string
  report_sections?: string[]
  clinical_indications?: string[]
  limitations?: string
  public_notes?: string
}
export type GeneEntry = Presentation & { key?: string; isgl_id?: string; subpanel_id?: string }
export type Category = Presentation & {
  catalog_id?: string | null
  asp_id?: string | null
  aspc_id?: string | null
  subpanel_id?: string | null
  aspc_ids?: Record<string, string>
  gene_lists?: GeneEntry[]
}
export type Modality = Presentation & { categories: Record<string, Category> }
export type Catalog = {
  header: string; description: string; maintainer?: string | null; version?: number
  layout: { order: string[] }; modalities: Record<string, Modality>
}
export type Version = {
  _id: string; revision: number; base_version: number; content_version: number | null
  status: "draft" | "submitted" | "approved" | "rejected" | "published"
  catalog: Catalog; created_by: string; updated_by: string; content_editors: string[]
  review: { reviewer?: string; publisher?: string; reviewer_reason?: string }
  lifecycle: { action: string; actor: string; occurred_at: string; reason?: string }[]
}
export type SourceOptions = {
  asps: { asp_id: string; label: string; category?: string; group?: string }[]
  aspcs: { aspc_id: string; asp_id: string; subpanel_id?: string }[]
  gene_lists: { isgl_id: string; label: string; asp_ids: string[]; diagnosis: string[] }[]
}
export type Workspace = {
  catalog: Catalog; has_published: boolean; sources: SourceOptions
  items: Omit<Version, "catalog">[]
  reviewers: { username: string; name: string }[]
  publishers: { username: string; name: string }[]
  presets: { analysis: string[]; input_material: string[]; sample_modes: string[] }
}
