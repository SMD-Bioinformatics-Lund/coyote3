import { useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { api } from "@/lib/api"
import { translocationAnnotationIdentity } from "@/lib/variant-helpers"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { CommentCard } from "@/components/comments/CommentCard"
import { FindingResourceType } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { cn } from "@/lib/utils"

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
  context: { assayGroup?: string; diagnosis?: string | null } = {},
) {
  const data: Record<string, any> = {
    text,
    asp_group: context.assayGroup,
    diagnosis_id: context.diagnosis,
  }
  if (global) data.global = "global"

  if (resourceType === "small_variant") {
    const csq = resource?.INFO?.selected_CSQ || {}
    const genomic = resource?.simple_id
      || (resource?.CHROM && resource?.POS ? `${resource.CHROM}_${resource.POS}_${resource.REF}_${resource.ALT}` : undefined)
    data.nomenclature = csq.HGVSp ? "p" : csq.HGVSc ? "c" : "g"
    data.variant = csq.HGVSp || csq.HGVSc || genomic
    data.hgvsp = csq.HGVSp
    data.hgvsc = csq.HGVSc
    data.genomic = genomic
    data.genomic_hash = resource?.simple_id_hash
    data.gene = csq.SYMBOL
    data.transcript = csq.Feature
  } else if (resourceType === "fusion") {
    const call = Array.isArray(resource?.calls) ? resource.calls.find((c: any) => c.selected) || resource.calls[0] : null
    data.nomenclature = "f"
    data.variant = [call?.breakpoint1, call?.breakpoint2].filter(Boolean).join("^") || resource?.breakpoints?.join("^")
    const genes = typeof resource?.genes === "string" ? resource.genes.split("^") : resource?.genes || []
    data.gene1 = resource?.gene1 || genes[0]
    data.gene2 = resource?.gene2 || genes[1]
  } else if (resourceType === "translocation") {
    data.nomenclature = "t"
    data.variant = resource?.CHROM && resource?.POS ? translocationAnnotationIdentity(resource) : undefined
    const ann = resource?.INFO?.MANE_ANN || resource?.INFO?.ANN?.[0] || {}
    const genes = typeof ann.Gene_Name === "string" ? ann.Gene_Name.split("&") : resource?.genes || []
    data.gene1 = genes[0]
    data.gene2 = genes[1]
  } else if (resourceType === "cnv") {
    data.nomenclature = "cn"
    data.variant = `${resource?.chr}:${resource?.start}-${resource?.end}`
  }

  return data
}

export interface CommentsPanelProps {
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
  onRequestSuggestion?: () => Promise<string | undefined>
  showList?: boolean
  showComposer?: boolean
  allowHide?: boolean
  assayGroup?: string
  diagnosis?: string | null
  draftText?: string
  onDraftChange?: (value: string) => void
  onUseAsDraft?: (value: string) => void
  fillHeight?: boolean
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
  onRequestSuggestion,
  showList = true,
  showComposer = true,
  allowHide = true,
  assayGroup,
  diagnosis,
  draftText,
  onDraftChange,
  onUseAsDraft,
  fillHeight = false,
}: CommentsPanelProps) {
  const [internalText, setInternalText] = useState("")
  const [global, setGlobal] = useState(false)
  const [mode, setMode] = useState<"edit" | "preview">("edit")
  const [isSuggestionLoading, setIsSuggestionLoading] = useState(false)
  const [showHiddenComments, setShowHiddenComments] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const currentUserQuery = useCurrentUserAccess()
  const text = draftText ?? internalText
  const setText = onDraftChange ?? setInternalText
  const isDetailComposer = Boolean(resourceType && resource)
  const selectedTranscript = resourceType === "small_variant"
    ? String(resource?.INFO?.selected_CSQ?.Feature || "").trim()
    : ""
  const showSuggestion = enableSuggestion ?? !isDetailComposer
  const showLivePreview = livePreview ?? !isDetailComposer
  const showPreviewToggle = previewToggle ?? isDetailComposer
  const permissionPrefix = resourceType ? "variant.comment" : "sample.comment"
  const canHideComments = allowHide && hasPermission(currentUserQuery.data, `${permissionPrefix}:hide`)
  const canUnhideComments = allowHide && hasPermission(currentUserQuery.data, `${permissionPrefix}:unhide`)
  const canViewHiddenComments = canHideComments && canUnhideComments
  const activeComments = comments.filter((comment) => !comment?.hidden)
  const hiddenComments = comments.filter((comment) => Boolean(comment?.hidden))
  const visibleComments = showHiddenComments && canViewHiddenComments
    ? comments
    : activeComments

  const invalidate = () => {
    queryKeys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }))
    queryClient.invalidateQueries({ queryKey: ["sample", sampleId] })
  }

  const addComment = useMutation({
    mutationFn: () => {
      if (resourceType && resource) {
        return api.post(`/samples/${sampleId}/annotations`, {
          id: String(resource._id),
          form_data: resourceFormData(resourceType, resource, text, global, { assayGroup, diagnosis }),
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
  const requestSuggestion = async () => {
    let suggestion = ""
    if (onRequestSuggestion) {
      setIsSuggestionLoading(true)
      try {
        suggestion = (await onRequestSuggestion())?.trim() || ""
      } finally {
        setIsSuggestionLoading(false)
      }
    } else {
      suggestion = suggestedText.trim()
    }
    if (!suggestion) return
    setMode("edit")
    setText(suggestion)
    onUseAsDraft?.(suggestion)
    textareaRef.current?.focus()
  }

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

  const escapeMarkdownSelection = () => {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    if (start === end) return
    const escaped = text.slice(start, end).replace(/([\\`*_[\]{}()#+\-.!>|~])/g, "\\$1")
    const next = `${text.slice(0, start)}${escaped}${text.slice(end)}`
    setText(next)
    window.setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(start, start + escaped.length)
    }, 0)
  }

  const toolbar = [
    { label: "Bold", icon: icon.bold, action: () => insertMarkdown("**", "**", "bold text") },
    { label: "Italic", icon: icon.italic, action: () => insertMarkdown("*", "*", "italic text") },
    { label: "Strikethrough", icon: icon.strikethrough, action: () => insertMarkdown("~~", "~~", "removed text") },
    { label: "Heading", icon: icon.heading, action: () => insertMarkdown("## ", "", "Heading", true) },
    { label: "Code", icon: icon.code, action: () => insertMarkdown("`", "`", "code") },
    { label: "Quote", icon: icon.quote, action: () => insertMarkdown("> ", "", "quote", true) },
    { label: "Bulleted list", icon: icon.list, action: () => insertMarkdown("- ", "", "list item", true) },
    { label: "Numbered list", icon: icon.listOrdered, action: () => insertMarkdown("1. ", "", "list item", true) },
    { label: "Link", icon: icon.link, action: () => insertMarkdown("[", "](https://)", "link text") },
    { label: "Table", icon: icon.table2, action: () => insertMarkdown("| Column | Value |\n| --- | --- |\n| ", " | value |", "item", true) },
    { label: "Horizontal rule", icon: icon.minus, action: () => insertMarkdown("---\n", "", "", true) },
    { label: "Escape Markdown", icon: icon.slash, action: escapeMarkdownSelection },
  ]

  return (
    <section className={cn("glass-card p-2.5", fillHeight && "flex h-full min-h-0 flex-col")}>
      <div className="mb-2 flex items-center gap-2">
        <icon.messageSquare className="h-4 w-4 text-tier2" />
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
        {showList && (
          <div className="ml-auto flex items-center gap-2">
            {canViewHiddenComments && hiddenComments.length > 0 && (
              <button
                type="button"
                onClick={() => setShowHiddenComments((current) => !current)}
                className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-card px-2 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-pressed={showHiddenComments}
              >
                {showHiddenComments
                  ? <icon.eyeOff className="size-3.5" aria-hidden="true" />
                  : <icon.eye className="size-3.5" aria-hidden="true" />}
                {showHiddenComments ? "Hide hidden" : `Show hidden (${hiddenComments.length})`}
              </button>
            )}
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">{activeComments.length}</span>
          </div>
        )}
      </div>

      {showList && <div className="max-h-160 space-y-2 overflow-y-auto p-1">
        {visibleComments.length ? visibleComments.map((comment, index) => (
          <CommentCard
            key={comment._id || index}
            comment={comment}
            selectedTranscript={selectedTranscript}
            allowHide={comment.hidden ? canUnhideComments : canHideComments}
            updating={toggleHidden.isPending}
            onUseAsDraft={(commentText) => {
              setText(commentText)
              onUseAsDraft?.(commentText)
              setMode("edit")
              window.setTimeout(() => textareaRef.current?.focus(), 0)
            }}
            onToggleHidden={comment._id && (comment.hidden ? canUnhideComments : canHideComments)
              ? () => toggleHidden.mutate({ commentId: String(comment._id), hidden: !comment.hidden })
              : undefined}
          />
        )) : (
          <div className="flex min-h-20 items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 p-4 text-sm text-muted-foreground">
            No comments available.
          </div>
        )}
      </div>}

      {showComposer && <div className={cn(
        "space-y-2 rounded-lg border border-border bg-background/60 p-2",
        showList && "mt-3",
        fillHeight && "flex min-h-0 flex-1 flex-col",
      )}>
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
          <>
            <button
              type="button"
              onClick={() => document.execCommand("undo")}
              title="Undo"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <icon.undo2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => document.execCommand("redo")}
              title="Redo"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <icon.redo2 className="h-4 w-4" />
            </button>
          </>
          {showSuggestion && (
            <>
              <span className="mx-1 h-6 w-px bg-border" />
              <button
                type="button"
                onClick={() => void requestSuggestion()}
                disabled={isSuggestionLoading || (!suggestedText.trim() && !onRequestSuggestion)}
                title={suggestedText.trim() || onRequestSuggestion ? "Insert suggested text" : "No suggested text available"}
                className="inline-flex items-center gap-1.5 rounded-md bg-validation/10 px-2 py-1.5 text-xs font-bold text-validation hover:bg-validation/20 disabled:opacity-45"
              >
                <icon.sparkles className="h-4 w-4" />
                {isSuggestionLoading ? "Preparing..." : "Suggest"}
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
                <icon.edit3 className="h-3.5 w-3.5" />
                Edit
              </button>
              <button
                type="button"
                onClick={() => setMode("preview")}
                className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${mode === "preview" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              >
                <icon.eye className="h-3.5 w-3.5" />
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
            className={cn(
              "min-h-52 w-full resize-y rounded-lg border border-input bg-background p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40",
              fillHeight && "flex-1",
            )}
          />
        ) : (
          <div className={cn("min-h-52 rounded-lg border border-input bg-background p-3", fillHeight && "flex-1")}>
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
            <icon.save className="h-3.5 w-3.5" />
            Save comment
          </button>
        </div>
        {showLivePreview && text && mode === "edit" && (
          <div className="rounded-lg border border-border bg-card p-2">
            <p className="mb-1 type-label font-semibold uppercase tracking-wider text-muted-foreground">Preview</p>
            <MarkdownText text={text} />
          </div>
        )}
      </div>}
    </section>
  )
}
