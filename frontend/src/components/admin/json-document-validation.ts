import { parse, printParseErrorCode, type ParseError } from "jsonc-parser"

export interface JsonDiagnostic {
  message: string
  line: number
  column: number
}

export type JsonValidation =
  | { valid: true; document: Record<string, unknown> }
  | {
      valid: false
      message: string
      line: number
      column: number
      diagnostics: JsonDiagnostic[]
    }

interface JsonSourceLocation {
  line: number
  column: number
}

function sourceLocationFromPosition(source: string, rawPosition: number): JsonSourceLocation {
  const position = Math.min(Math.max(rawPosition, 0), source.length)
  const beforeError = source.slice(0, position)
  const line = beforeError.split("\n").length
  const lastNewline = beforeError.lastIndexOf("\n")
  return { line, column: position - lastNewline }
}

function parseErrorMessage(error: ParseError): string {
  const description = printParseErrorCode(error.error)
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
  return `JSON syntax error: ${description}.`
}

export function validateJsonDocument(source: string): JsonValidation {
  const errors: ParseError[] = []
  const parsed = parse(source, errors, {
    allowEmptyContent: false,
    allowTrailingComma: false,
    disallowComments: true,
  })

  if (errors.length) {
    const diagnostics = errors.map((error) => ({
      ...sourceLocationFromPosition(source, error.offset),
      message: parseErrorMessage(error),
    }))
    return {
      valid: false,
      message: diagnostics[0].message,
      line: diagnostics[0].line,
      column: diagnostics[0].column,
      diagnostics,
    }
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    const diagnostic = {
      message: "The sample document must be a JSON object.",
      line: 1,
      column: 1,
    }
    return {
      valid: false,
      ...diagnostic,
      diagnostics: [diagnostic],
    }
  }

  return { valid: true, document: parsed as Record<string, unknown> }
}
