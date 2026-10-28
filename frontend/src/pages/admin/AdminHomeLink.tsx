import { icon } from "@/lib/assets"
import { Link } from "react-router-dom"

export function AdminHomeLink() {
  return <Link to="/admin" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 type-body-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
    <icon.arrowLeft className="size-4" aria-hidden="true" />Administration
  </Link>
}
