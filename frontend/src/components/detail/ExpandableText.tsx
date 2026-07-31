import { useState } from "react"
import { Copy, Check, ChevronUp } from "lucide-react"

interface ExpandableTextProps {
  text: string
  maxLength?: number
  className?: string
}

export function ExpandableText({ text, maxLength = 25, className = "" }: ExpandableTextProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!text || text === "-") return <span className={className}>-</span>

  const isLong = text.length > maxLength
  const displayText = isExpanded ? text : (isLong ? `${text.substring(0, maxLength)}...` : text)

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`flex items-start gap-1 group/expandable ${className}`}>
      <span className="break-all">{displayText}</span>

      {isLong && (
        <button
          onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded) }}
          className="text-primary hover:text-primary/80 font-bold ml-1 shrink-0 p-0.5 rounded hover:bg-muted"
          title={isExpanded ? "Collapse" : "Expand"}
        >
          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <span className="text-[10px] bg-primary/10 px-1 py-0.5 rounded leading-none">+{text.length - maxLength}</span>}
        </button>
      )}

      <button
        onClick={handleCopy}
        className={`shrink-0 p-1 rounded transition-opacity ${copied ? 'text-pass opacity-100' : 'text-muted-foreground opacity-0 group-hover/expandable:opacity-100 hover:text-foreground hover:bg-muted'}`}
        title="Copy to clipboard"
      >
        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      </button>
    </div>
  )
}
