// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { LoadingIndicator } from "@/components/ui/loading-indicator"
import { useEffect, useEffectEvent, useId, useRef } from "react"
import type { ReactNode } from "react"
import { createPortal } from "react-dom"
import { icon } from "@/lib/assets"
import { Button } from "@/components/ui/button"
import { Surface } from "@/components/ui/surface"

type ConfirmationDialogProps = {
  open: boolean
  title: string
  description: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  isPending?: boolean
  confirmDisabled?: boolean
  variant?: "default" | "destructive"
  onConfirm: () => void | Promise<unknown>
  onCancel: () => void
}

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isPending = false,
  confirmDisabled = false,
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const titleId = useId()
  const descriptionId = useId()
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const handleKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault()
      event.stopPropagation()
      if (!isPending) onCancel()
    }
    if (event.key !== "Tab") return
    const controls = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("*") ?? [])
      .filter(element => element.tabIndex >= 0 && !element.matches(":disabled") && !element.closest('[hidden], [aria-hidden="true"]'))
    const first = controls[0]
    const last = controls.at(-1)
    if (!first) {
      event.preventDefault()
      dialogRef.current?.focus()
    } else if (!dialogRef.current?.contains(document.activeElement) || (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
      event.preventDefault()
      const target = event.shiftKey ? last : first
      target?.focus()
    }
  })

  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    if (cancelButtonRef.current?.disabled) dialogRef.current?.focus()
    else cancelButtonRef.current?.focus()
    const listener = (event: KeyboardEvent) => handleKeyDown(event)
    document.addEventListener("keydown", listener)
    return () => {
      document.removeEventListener("keydown", listener)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-background/55 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isPending) onCancel()
      }}
    >
      <Surface
        ref={dialogRef}
        tabIndex={-1}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="glass-card max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto border border-border/80 bg-card p-5 shadow-2xl"
      >
        <div className="flex items-start gap-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-warn/35 bg-warn/12 text-warn">
            <icon.alertTriangle className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 id={titleId} className="text-sm font-semibold text-foreground">{title}</h2>
            <div id={descriptionId} className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              {description}
            </div>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm"
            ref={cancelButtonRef}
            type="button"
            onClick={onCancel}
            disabled={isPending}
          >
            <icon.x className="size-3.5" aria-hidden="true" />
            {cancelLabel}
          </Button>
          <Button variant={variant} size="sm"
            type="button"
            onClick={onConfirm}
            disabled={isPending || confirmDisabled}
          >
            {isPending ? (
              <LoadingIndicator className="size-3.5" />
            ) : (
              <icon.check className="size-3.5" aria-hidden="true" />
            )}
            {isPending ? "Applying" : confirmLabel}
          </Button>
        </div>
      </Surface>
    </div>,
    document.body,
  )
}
