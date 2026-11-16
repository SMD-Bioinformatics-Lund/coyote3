// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { markdownToHtml } from "./markdown-format"

export function MarkdownText({
  text,
  className = "",
}: {
  text?: string
  className?: string
}) {
  return (
    <div
      className={`markdown-body text-sm leading-relaxed ${className}`}
      dangerouslySetInnerHTML={{ __html: markdownToHtml(text || "") }}
    />
  )
}
