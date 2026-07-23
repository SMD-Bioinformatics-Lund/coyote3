import { useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Bold,
  Code,
  Edit3,
  Eye,
  EyeOff,
  Heading,
  Italic,
  Link,
  List,
  ListOrdered,
  Minus,
  MessageSquare,
  Quote,
  Redo2,
  Save,
  Sparkles,
  Strikethrough,
  Table2,
  Undo2,
} from "lucide-react"
import { api } from "@/lib/api"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { FindingResourceType } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { fullDateTime, humanRelativeDate } from "@/lib/detail-formatters"

function dateLabel(value: unknown) {
  return humanRelativeDate(value, "")
}

function fullDateLabel(value: unknown) {
  return fullDateTime(value, "")
}

const pathByResource: Record<FindingResourceType, string> = {
  small_variant: "small-variants",
  cnv: "cnvs",
  fusion: "fusions",
  translocation: "translocations",
}

function resourceFormData(
  resourceType: FindingResourceType,
  resource: any,
  text: string,
  global: boolean,
  context: { assayGroup?: string; subpanel?: string | null } = {},
) {
  const data: Record<string, any> = {
    text,
    assay_group: context.assayGroup,
    subpanel: context.subpanel,
  }
  if (global) data.global = "global"

  if (resourceType === "small_variant") {
    const csq = resource?.INFO?.selected_CSQ || {}
    data.var_p = csq.HGVSp
    data.var_c = csq.HGVSc
    data.var_g = resource?.CHROM && resource?.POS ? `${resource.CHROM}:${resource.POS}:${resource.REF}/${resource.ALT}` : undefined
    data.gene = csq.SYMBOL
    data.transcript = csq.Feature
  } else if (resourceType === "fusion") {
    const call = Array.isArray(resource?.calls) ? resource.calls.find((c: any) => c.selected) || resource.calls[0] : null
    data.fusionpoints = [call?.breakpoint1, call?.breakpoint2].filter(Boolean).join("^") || resource?.breakpoints?.join("^")
    const genes = typeof resource?.genes === "string" ? resource.genes.split("^") : resource?.genes || []
    data.gene1 = resource?.gene1 || genes[0]
    data.gene2 = resource?.gene2 || genes[1]
  } else if (resourceType === "translocation") {
    data.translocpoints = resource?.CHROM && resource?.POS ? `${resource.CHROM}:${resource.POS}^${Array.isArray(resource?.ALT) ? resource.ALT[0] : resource?.ALT}` : undefined
    const ann = resource?.INFO?.MANE_ANN || resource?.INFO?.ANN?.[0] || {}
    const genes = typeof ann.Gene_Name === "string" ? ann.Gene_Name.split("&") : resource?.genes || []
    data.gene1 = genes[0]
    data.gene2 = genes[1]
  } else if (resourceType === "cnv") {
    data.cnvvar = `${resource?.chr}:${resource?.start}-${resource?.end}`
    data.gene = resource?.genes?.[0]?.gene
  }

  return data
}

function fallbackSuggestedText(resourceType?: FindingResourceType, resource?: any) {
  if (!resourceType || !resource) return ""
  if (resourceType === "small_variant") {
    const csq = resource?.INFO?.selected_CSQ || {}
    const gene = csq.SYMBOL || resource?.gene || "The variant"
    const protein = csq.HGVSp || resource?.hgvsp || ""
    const cdna = csq.HGVSc || resource?.hgvsc || ""
    const tier = resource?.classification?.class ? `tier ${resource.classification.class}` : "currently tiered"
    return [`${gene} ${protein || cdna}`.trim(), `is ${tier}.`].filter(Boolean).join(" ")
  }
  if (resourceType === "cnv") {
    const genes = Array.isArray(resource?.genes)
      ? resource.genes.map((gene: any) => gene?.gene).filter(Boolean).join(", ")
      : resource?.gene || "The CNV"
    const region = [resource?.chr, resource?.start, resource?.end].filter(Boolean).join(":")
    return `${genes || "The CNV"} shows a copy-number change${region ? ` at ${region}` : ""}.`
  }
  if (resourceType === "fusion") {
    const genes = resource?.gene1 && resource?.gene2 ? `${resource.gene1}-${resource.gene2}` : resource?.genes
    return `${genes || "The fusion"} is selected for clinical review.`
  }
  if (resourceType === "translocation") {
    return "The translocation is selected for clinical review."
  }
  return ""
}

export function CommentsPanel({
  sampleId,
  comments = [],
  title = "Comments",
  resourceType,
  resource,
  queryKeys = [],
  allowGlobal = true,
  enableSuggestion,
  livePreview,
  previewToggle,
  suggestedText = "",
  showList = true,
  showComposer = true,
  allowHide = true,
  assayGroup,
  subpanel,
  draftText,
  onDraftChange,
  onUseAsDraft,
}: {
  sampleId: string
  comments?: any[]
  title?: string
  resourceType?: FindingResourceType
  resource?: any
  queryKeys?: unknown[][]
  allowGlobal?: boolean
  enableSuggestion?: boolean
  livePreview?: boolean
  previewToggle?: boolean
  suggestedText?: string
  showList?: boolean
  showComposer?: boolean
  allowHide?: boolean
  assayGroup?: string
  subpanel?: string | null
  draftText?: string
  onDraftChange?: (value: string) => void
  onUseAsDraft?: (value: string) => void
}) {
  const [internalText, setInternalText] = useState("")
  const [global, setGlobal] = useState(false)
  const [mode, setMode] = useState<"edit" | "preview">("edit")
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const text = draftText ?? internalText
  const setText = onDraftChange ?? setInternalText
  const isDetailComposer = Boolean(resourceType && resource)
  const showSuggestion = enableSuggestion ?? !isDetailComposer
  const showLivePreview = livePreview ?? !isDetailComposer
  const showPreviewToggle = previewToggle ?? isDetailComposer

  const invalidate = () => {
    queryKeys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }))
    queryClient.invalidateQueries({ queryKey: ["sample", sampleId] })
  }

  const addComment = useMutation({
    mutationFn: () => {
      if (resourceType && resource) {
        return api.post(`/samples/${sampleId}/annotations`, {
          id: String(resource._id),
          form_data: resourceFormData(resourceType, resource, text, global, { assayGroup, subpanel }),
        })
      }
      return api.post(`/samples/${sampleId}/comments`, { form_data: { sample_comment: text } })
    },
    onSuccess: () => {
      setText("")
      setGlobal(false)
      invalidate()
      notifySuccess("Comment saved", "The markdown comment was saved.", "Comments")
    },
    onError: (error) => {
      notifyActionError("Unable to save comment", error, "Comments")
    },
  })
  const effectiveSuggestedText = suggestedText.trim() || fallbackSuggestedText(resourceType, resource)

  const toggleHidden = useMutation({
    mutationFn: ({ commentId, hidden }: { commentId: string; hidden: boolean }) => {
      if (resourceType && resource) {
        const method = hidden ? api.patch : api.delete
        return method(`/samples/${sampleId}/${pathByResource[resourceType]}/${resource._id}/comments/${commentId}/hidden`, {})
      }
      const method = hidden ? api.patch : api.delete
      return method(`/samples/${sampleId}/comments/${commentId}/hidden`, {})
    },
    onSuccess: (_result, variables) => {
      invalidate()
      notifySuccess(
        variables.hidden ? "Comment hidden" : "Comment restored",
        variables.hidden ? "The comment is hidden from the active view." : "The comment is visible again.",
        "Comments"
      )
    },
    onError: (error) => {
      notifyActionError("Unable to update comment", error, "Comments")
    },
  })

  const insertMarkdown = (before: string, after = "", placeholder = "text", block = false) => {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selected = text.slice(start, end) || placeholder
    const prefix = block && start > 0 && text[start - 1] !== "\n" ? "\n" : ""
    const next = `${text.slice(0, start)}${prefix}${before}${selected}${after}${text.slice(end)}`
    const cursorStart = start + prefix.length + before.length
    const cursorEnd = cursorStart + selected.length
    setText(next)
    window.setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(cursorStart, cursorEnd)
    }, 0)
  }

  const toolbar = [
    { label: "Bold", icon: Bold, action: () => insertMarkdown("**", "**", "bold text") },
    { label: "Italic", icon: Italic, action: () => insertMarkdown("*", "*", "italic text") },
    { label: "Strikethrough", icon: Strikethrough, action: () => insertMarkdown("~~", "~~", "removed text") },
    { label: "Heading", icon: Heading, action: () => insertMarkdown("## ", "", "Heading", true) },
    { label: "Code", icon: Code, action: () => insertMarkdown("`", "`", "code") },
    { label: "Quote", icon: Quote, action: () => insertMarkdown("> ", "", "quote", true) },
    { label: "Bulleted list", icon: List, action: () => insertMarkdown("- ", "", "list item", true) },
    { label: "Numbered list", icon: ListOrdered, action: () => insertMarkdown("1. ", "", "list item", true) },
    { label: "Link", icon: Link, action: () => insertMarkdown("[", "](https://)", "link text") },
    { label: "Table", icon: Table2, action: () => insertMarkdown("| Column | Value |\n| --- | --- |\n| ", " | value |", "item", true) },
    { label: "Horizontal rule", icon: Minus, action: () => insertMarkdown("---\n", "", "", true) },
  ]

  const useSuggestion = () => {
    if (!effectiveSuggestedText.trim()) return
    setText(effectiveSuggestedText.trim())
    setMode("edit")
    window.setTimeout(() => textareaRef.current?.focus(), 0)
  }

  return (
    <section className="glass-card border-t-4 border-t-tier2 p-2.5">
      <div className="mb-2 flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-tier2" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">{title}</h3>
        {showList && (
          <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs font-bold text-muted-foreground">{comments.length}</span>
        )}
      </div>

      {showList && <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
        {comments.length ? comments.map((comment, index) => (
          <div key={comment._id || index} className={`rounded-lg border border-border bg-background/70 p-2 ${comment.hidden ? "opacity-55" : ""}`}>
            <div className="mb-1 flex items-center justify-between gap-2 text-xs">
              <span className="font-bold">{comment.author || comment.user || "Unknown"}</span>
              <span className="text-muted-foreground" title={fullDateLabel(comment.time_created || comment.created_at)}>
                {dateLabel(comment.time_created || comment.created_at)}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                const commentText = comment.text || comment.comment || ""
                setText(commentText)
                onUseAsDraft?.(commentText)
                setMode("edit")
                window.setTimeout(() => textareaRef.current?.focus(), 0)
              }}
              className="block w-full text-left"
              title="Load this comment into the editor"
            >
              <MarkdownText text={comment.text || comment.comment || ""} />
            </button>
            <div className="mt-2 flex flex-wrap gap-2">
            {allowHide && comment._id && (
              <button
                onClick={() => toggleHidden.mutate({ commentId: String(comment._id), hidden: !comment.hidden })}
                disabled={toggleHidden.isPending}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-semibold hover:bg-muted"
              >
                {comment.hidden ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                {comment.hidden ? "Unhide" : "Hide"}
              </button>
            )}
            </div>
          </div>
        )) : (
          <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">No comments available.</p>
        )}
      </div>}

      {showComposer && <div className={showList ? "mt-3 space-y-2 rounded-lg border border-border bg-background/60 p-2" : "space-y-2 rounded-lg border border-border bg-background/60 p-2"}>
        <div className="flex flex-wrap items-center gap-1 rounded-lg border border-border bg-card/80 p-1">
          {toolbar.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={item.action}
              title={item.label}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <item.icon className="h-4 w-4" />
            </button>
          ))}
          <span className="mx-1 h-6 w-px bg-border" />
          <button
            type="button"
            onClick={() => document.execCommand("undo")}
            title="Undo"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Undo2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => document.execCommand("redo")}
            title="Redo"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Redo2 className="h-4 w-4" />
          </button>
          {showSuggestion && (
            <>
              <span className="mx-1 h-6 w-px bg-border" />
              <button
                type="button"
                onClick={useSuggestion}
                disabled={!effectiveSuggestedText.trim()}
                title={effectiveSuggestedText.trim() ? "Insert suggested text" : "No suggested text available"}
                className="inline-flex items-center gap-1.5 rounded-md bg-validation/10 px-2 py-1.5 text-xs font-bold text-validation hover:bg-validation/20 disabled:opacity-45"
              >
                <Sparkles className="h-4 w-4" />
                Suggest
              </button>
            </>
          )}
          {showPreviewToggle && (
            <div className="ml-auto flex rounded-md border border-border bg-background p-0.5">
              <button
                type="button"
                onClick={() => setMode("edit")}
                className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${mode === "edit" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              >
                <Edit3 className="h-3.5 w-3.5" />
                Edit
              </button>
              <button
                type="button"
                onClick={() => setMode("preview")}
                className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${mode === "preview" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              >
                <Eye className="h-3.5 w-3.5" />
                Preview
              </button>
            </div>
          )}
        </div>
        {mode === "edit" ? (
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Write a markdown comment..."
            className="min-h-52 w-full resize-y rounded-lg border border-input bg-background p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          />
        ) : (
          <div className="min-h-52 rounded-lg border border-input bg-background p-3">
            {text.trim() ? <MarkdownText text={text} /> : <p className="text-sm text-muted-foreground">Nothing to preview.</p>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {resourceType && allowGlobal && (
            <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <input type="checkbox" checked={global} onChange={(event) => setGlobal(event.target.checked)} />
              Global annotation
            </label>
          )}
          <button
            onClick={() => addComment.mutate()}
            disabled={!text.trim() || addComment.isPending}
            className="ml-auto inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            Save comment
          </button>
        </div>
        {showLivePreview && text && mode === "edit" && (
          <div className="rounded-lg border border-border bg-card p-2">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Preview</p>
            <MarkdownText text={text} />
          </div>
        )}
      </div>}
    </section>
  )
}
