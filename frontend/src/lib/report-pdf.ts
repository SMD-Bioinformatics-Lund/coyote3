/** Reject error pages and incomplete responses before opening the browser PDF viewer. */
export async function validateReportPdf(blob: Blob): Promise<Blob> {
  const signature = await blob.slice(0, 5).text()
  const tail = await blob.slice(Math.max(0, blob.size - 1024)).text()
  if (signature !== "%PDF-" || !tail.trimEnd().endsWith("%%EOF")) {
    throw Object.assign(new Error("The PDF response is invalid or incomplete. Retry the preview."), {
      handledInline: true,
    })
  }
  return blob.type === "application/pdf" ? blob : new Blob([blob], { type: "application/pdf" })
}
