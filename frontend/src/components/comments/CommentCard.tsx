import { Dna, Eye, EyeOff, Globe2, PencilLine, UserRound } from "lucide-react"

import { MarkdownText } from "@/components/comments/MarkdownText"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { TimeDisplay } from "@/components/ui/time-display"

function commentText(comment: any) {
  return String(comment?.text || comment?.comment || "")
}

function commentAuthor(comment: any) {
  return String(comment?.author || comment?.user || "Unknown")
}

function authorInitials(author: string) {
  const parts = author.trim().split(/[.\s_-]+/).filter(Boolean)
  if (!parts.length || author === "Unknown") return null
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("")
}

function isGlobalComment(comment: any) {
  return comment?.global === true
    || comment?.global === "global"
    || comment?.scope === "global"
    || comment?.assay === "global"
}

export function CommentCard({
  comment,
  dateDisplay = "relative",
  onUseAsDraft,
  onToggleHidden,
  allowHide = true,
  updating = false,
  selectedTranscript,
}: {
  comment: any
  dateDisplay?: "relative" | "full"
  onUseAsDraft?: (text: string) => void
  onToggleHidden?: () => void
  allowHide?: boolean
  updating?: boolean
  selectedTranscript?: string
}) {
  const text = commentText(comment)
  const author = commentAuthor(comment)
  const initials = authorInitials(author)
  const hidden = Boolean(comment?.hidden)
  const createdAt = comment?.time_created || comment?.created_at
  const commentTranscript = String(comment?.transcript || "").trim()
  const currentTranscript = String(selectedTranscript || "").trim()
  const hasDifferentTranscript = Boolean(
    commentTranscript
    && currentTranscript
    && commentTranscript !== currentTranscript,
  )
  const bodyClasses = [
    "group/comment-body block w-full rounded-md border px-3 py-2.5 text-left transition-colors",
    hidden
      ? "cursor-default border-border/60 bg-muted/35 text-muted-foreground"
      : "border-border/80 bg-card hover:border-primary/35 hover:bg-primary/[0.025] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
  ].join(" ")

  return (
    <article
      className={[
        "rounded-lg border bg-card p-3 shadow-sm transition-colors",
        hidden ? "border-border/60 opacity-50" : "border-border hover:border-border/90",
      ].join(" ")}
    >
      <header className="mb-2.5 flex min-w-0 items-start gap-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/15 bg-primary/8 type-meta font-semibold text-primary">
          {initials || <UserRound className="size-4" aria-hidden="true" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-semibold text-foreground">{author}</span>
            {isGlobalComment(comment) && (
              <span className="inline-flex items-center gap-1 rounded-full border border-info/25 bg-info/10 px-1.5 py-0.5 type-label font-medium text-info">
                <Globe2 className="size-3" aria-hidden="true" />
                Global
              </span>
            )}
            {hasDifferentTranscript && (
              <AppTooltip
                context="Transcript-specific annotation"
                label={`Authored for ${commentTranscript}`}
                content={`This annotation belongs to transcript ${commentTranscript}. The currently selected transcript is ${currentTranscript}.`}
              >
                <span className="inline-flex items-center gap-1 rounded-full border border-info/25 bg-info/10 px-1.5 py-0.5 type-label font-medium text-info">
                  <Dna className="size-3" aria-hidden="true" />
                  Transcript {commentTranscript}
                </span>
              </AppTooltip>
            )}
            {hidden && (
              <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-1.5 py-0.5 type-label font-medium text-muted-foreground">
                <EyeOff className="size-3" aria-hidden="true" />
                Hidden
              </span>
            )}
          </div>
          {createdAt && (
            <TimeDisplay
              value={createdAt}
              mode={dateDisplay}
              fallback=""
              className="mt-0.5 text-xs text-muted-foreground"
            />
          )}
        </div>
      </header>

      {onUseAsDraft ? (
        <button
          type="button"
          disabled={hidden}
          onClick={() => onUseAsDraft(text)}
          className={bodyClasses}
          title={hidden ? undefined : "Load this comment into the editor"}
        >
          <MarkdownText text={text || "-"} />
          {!hidden && (
            <span aria-hidden="true" className="mt-2 flex items-center gap-1 border-t border-border/60 pt-2 type-meta font-medium text-muted-foreground opacity-0 transition-opacity group-hover/comment-body:opacity-100 group-focus-visible/comment-body:opacity-100">
              <PencilLine className="size-3" />
              Use as draft
            </span>
          )}
        </button>
      ) : (
        <div className={bodyClasses}>
          <MarkdownText text={text || "-"} />
        </div>
      )}

      {allowHide && onToggleHidden && comment?._id && (
        <footer className="mt-2.5 flex justify-end border-t border-border/60 pt-2">
          <button
            type="button"
            onClick={onToggleHidden}
            disabled={updating}
            className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            {hidden ? <Eye className="size-3.5" aria-hidden="true" /> : <EyeOff className="size-3.5" aria-hidden="true" />}
            {hidden ? "Unhide" : "Hide"}
          </button>
        </footer>
      )}
    </article>
  )
}
