import { useEffect, useRef, type ChangeEvent } from "react"

type RowSelectionCheckboxProps = {
  checked: boolean
  indeterminate?: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  label: string
}

export function RowSelectionCheckbox({
  checked,
  indeterminate = false,
  onChange,
  label,
}: RowSelectionCheckboxProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = indeterminate
  }, [indeterminate])

  return (
    <div className="flex w-full items-center justify-center">
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="table-checkbox"
        aria-label={label}
      />
    </div>
  )
}
