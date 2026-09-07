import { useState } from "react";
import { Copy, Check, ChevronUp } from "lucide-react";

interface ExpandableTextProps {
  text: string;
  maxLength?: number;
  className?: string;
}

export function ExpandableText({ text, maxLength = 25, className = "" }: ExpandableTextProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!text || text === "-") return <span className={className}>-</span>;

  const isLong = text.length > maxLength;
  const displayText = isExpanded ? text : isLong ? `${text.substring(0, maxLength)}...` : text;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group/expandable flex min-w-0 max-w-full items-start gap-1 overflow-hidden ${className}`}
    >
      <span className="min-w-0 flex-1 whitespace-normal [overflow-wrap:anywhere] [word-break:break-word]">
        {displayText}
      </span>

      {isLong && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="ml-1 shrink-0 rounded p-0.5 font-semibold text-primary interaction-transition hover:bg-surface-hover hover:text-primary/80"
          title={isExpanded ? "Collapse" : "Expand"}
          aria-label={isExpanded ? "Collapse full value" : "Show full value"}
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <ChevronUp className="w-3 h-3" />
          ) : (
            <span className="type-label bg-primary/10 px-1 py-0.5 rounded leading-none">
              +{text.length - maxLength}
            </span>
          )}
        </button>
      )}

      <button
        onClick={handleCopy}
        className={`shrink-0 rounded p-1 interaction-transition ${copied ? "text-pass opacity-100" : "text-muted-foreground opacity-0 group-hover/expandable:opacity-100 hover:bg-surface-hover hover:text-foreground"}`}
        title="Copy to clipboard"
      >
        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      </button>
    </div>
  );
}
