// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/** Resolve existing control names and help text, never entered field values. */
const CONTROL_SELECTOR = [
  "button", "a[href]", "input:not([type='hidden'])", "select", "textarea", "summary",
  "[role='button']", "[role='link']", "[role='tab']", "[role='checkbox']",
  "[role='radio']", "[role='switch']", "[role='combobox']", "[role='menuitem']",
  "[role='slider']", "[role='spinbutton']", "[data-slot='badge']", "[data-slot='table-badge']",
].join(",")

export const GLOBAL_TOOLTIP_ID = "global-rich-tooltip"

export function tooltipTarget(value: EventTarget | null): HTMLElement | null {
  if (!(value instanceof Element)) return null
  // Rich badges own their hints; never open a second tooltip on an ancestor.
  if (value.closest('[data-tooltip-managed="true"], [data-native-title="true"], [data-tooltip-disabled="true"], [role="tooltip"]')) return null
  const target = value.closest(`[data-tooltip-content], [title]:not(iframe), ${CONTROL_SELECTOR}`)
  return target instanceof HTMLElement && !(target instanceof HTMLIFrameElement) ? target : null
}

function labelText(element: Element): string {
  const copy = element.cloneNode(true) as Element
  copy.querySelectorAll('svg, [aria-hidden="true"], [hidden], input, select, textarea').forEach(node => node.remove())
  copy.querySelectorAll("img[alt]").forEach(image => image.replaceWith(image.getAttribute("alt") || ""))
  return (copy.textContent || "").replace(/\s+/g, " ").trim()
}

function referencedText(target: HTMLElement, attribute: string): string {
  return (target.getAttribute(attribute) || "").split(/\s+/)
    .filter(id => id && id !== GLOBAL_TOOLTIP_ID)
    .map(id => target.ownerDocument.getElementById(id))
    .filter((element): element is HTMLElement => Boolean(element))
    .map(labelText).filter(Boolean).join(" ")
}

function controlLabel(target: HTMLElement): string {
  const explicit = referencedText(target, "aria-labelledby") || target.getAttribute("aria-label")?.trim()
  if (explicit) return explicit
  if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement) {
    const label = Array.from(target.labels || []).map(labelText).filter(Boolean).join(" ")
    if (label) return label
    // A submit/button value is a caption. All other input values may be sensitive.
    if (target instanceof HTMLInputElement && ["button", "submit", "reset"].includes(target.type)) {
      return target.getAttribute("value") || (target.type === "submit" ? "Submit" : target.type === "reset" ? "Reset" : "")
    }
    return target.getAttribute("placeholder")?.trim() || ""
  }
  return target.matches(CONTROL_SELECTOR) ? labelText(target) : ""
}

function visibleLabel(target: HTMLElement): string {
  if (target.matches('svg, img, input, select, textarea, [aria-hidden="true"], [hidden], .sr-only')) return ""
  const style = getComputedStyle(target)
  if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return ""
  return Array.from(target.childNodes).map(node => node.nodeType === Node.TEXT_NODE
    ? node.textContent || "" : node instanceof HTMLElement ? visibleLabel(node) : "")
    .join(" ").replace(/\s+/g, " ").trim()
}

function visibleControlLabel(target: HTMLElement): string {
  if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement) {
    if (target instanceof HTMLInputElement && ["button", "submit", "reset"].includes(target.type)) return controlLabel(target)
    return Array.from(target.labels || []).map(visibleLabel).filter(Boolean).join(" ")
      || target.getAttribute("placeholder")?.trim() || ""
  }
  return visibleLabel(target)
}

function clippedLabel(target: HTMLElement): boolean {
  return [target, ...target.querySelectorAll<HTMLElement>('.truncate, [class*="line-clamp-"]')]
    .some(element => {
      if (!element.clientWidth || !element.clientHeight) return false
      const style = getComputedStyle(element)
      return (["hidden", "clip"].includes(style.overflowX) && element.scrollWidth > element.clientWidth)
        || (["hidden", "clip"].includes(style.overflowY) && element.scrollHeight > element.clientHeight)
    })
}

export function tooltipContent(target: HTMLElement) {
  const name = controlLabel(target)
  const help = target.dataset.tooltipContent?.trim() || target.getAttribute("title")?.trim()
    || referencedText(target, "aria-describedby")
  const visible = visibleControlLabel(target)
  const clipped = Boolean(visible) && clippedLabel(target)
  if (help) {
    // A title that only repeats the readable caption adds no information.
    if (help.replace(/\s+/g, " ").toLowerCase() === visible.toLowerCase() && !clipped) return null
  } else {
    const field = target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement
      || (target instanceof HTMLInputElement && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(target.type))
    if (field || (visible && !clipped)) return null
  }
  const title = help || name
  if (!title) return null
  return {
    title,
    label: target.dataset.tooltipLabel || name || title,
    context: target.dataset.tooltipContext || "More information",
    tone: target.dataset.tooltipTone || "info",
  }
}
