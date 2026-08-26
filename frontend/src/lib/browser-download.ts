/** Trigger a browser download and release the temporary object URL afterwards. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.style.display = "none"
  document.body.appendChild(anchor)
  try {
    anchor.click()
  } finally {
    anchor.remove()
    // Chromium may cancel a download when the URL is revoked in the same task.
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }
}

export function downloadText(content: string, filename: string, mimeType: string): void {
  downloadBlob(new Blob([content], { type: mimeType }), filename)
}
