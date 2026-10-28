import { expect, it } from "vitest"
import { validateReportPdf } from "./report-pdf"

it("retains PDF bytes and supplies the MIME type required by embedded viewers", async () => {
  const pdf = "%PDF-1.7\nSynthetic report\n%%EOF\n"
  const result = await validateReportPdf(new Blob([pdf], { type: "application/octet-stream" }))
  expect(result.type).toBe("application/pdf")
  expect(await result.text()).toBe(pdf)
})

it.each(["", "<html>Sign in</html>", '{"detail":"Unavailable"}', "%PDF-1.7\ntruncated"])(
  "rejects invalid or incomplete PDF data: %s", async content => {
    await expect(validateReportPdf(new Blob([content]))).rejects.toThrow("invalid or incomplete")
  },
)
