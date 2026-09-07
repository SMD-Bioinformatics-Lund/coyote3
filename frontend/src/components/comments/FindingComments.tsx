import { CommentsPanel, type CommentsPanelProps } from "@/components/comments/CommentsPanel"
import type { FindingResourceType } from "@/lib/finding-actions"

interface FindingCommentBaseProps {
  sampleId: string
  resourceType: FindingResourceType
  resource: unknown
  queryKeys: unknown[][]
}

interface FindingCommentComposerProps extends FindingCommentBaseProps {
  assayGroup?: string
  subpanel?: string | null
  draftText?: string
  onDraftChange?: (value: string) => void
}

interface FindingCommentListsProps extends FindingCommentBaseProps {
  findingLabel: string
  sampleComments?: CommentsPanelProps["comments"]
  globalComments?: CommentsPanelProps["comments"]
  onUseAsDraft?: (value: string) => void
}

export function FindingCommentComposer({
  sampleId,
  resourceType,
  resource,
  queryKeys,
  assayGroup,
  subpanel,
  draftText,
  onDraftChange,
}: FindingCommentComposerProps) {
  return (
    <div className="h-full lg:col-span-2">
      <CommentsPanel
        sampleId={sampleId}
        title="Add Comment Or Annotation"
        resourceType={resourceType}
        resource={resource}
        comments={[]}
        showList={false}
        assayGroup={assayGroup}
        subpanel={subpanel}
        queryKeys={queryKeys}
        enableSuggestion={false}
        livePreview={false}
        draftText={draftText}
        onDraftChange={onDraftChange}
        fillHeight
      />
    </div>
  )
}

export function FindingCommentLists({
  sampleId,
  resourceType,
  resource,
  queryKeys,
  findingLabel,
  sampleComments = [],
  globalComments = [],
  onUseAsDraft,
}: FindingCommentListsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <CommentsPanel
        sampleId={sampleId}
        title={`Sample-Specific ${findingLabel} Comments`}
        resourceType={resourceType}
        resource={resource}
        comments={sampleComments}
        showComposer={false}
        queryKeys={queryKeys}
        onUseAsDraft={onUseAsDraft}
      />
      <CommentsPanel
        sampleId={sampleId}
        title={`Global ${findingLabel} Annotations`}
        resourceType={resourceType}
        resource={resource}
        comments={globalComments}
        showComposer={false}
        allowHide={false}
        queryKeys={queryKeys}
        onUseAsDraft={onUseAsDraft}
      />
    </div>
  )
}
