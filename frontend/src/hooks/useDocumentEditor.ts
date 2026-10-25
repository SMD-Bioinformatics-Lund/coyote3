import { api } from "@/lib/api"
import { useEffect, useRef, useState } from "react"

type Lease = { owned: boolean; owner: string | null; expires_at: string | null; renew_after_seconds: number }
type State = { key: string; session: string; lease: Lease | null; error: string }

/** Take a short editing session for a version-checked action without a persistent form. */
export async function withDocumentEditor<T>(kind: string, identity: string, action: (options: RequestInit) => Promise<T>): Promise<T> {
  const editor_id = crypto.randomUUID()
  const path = `/editing/${encodeURIComponent(kind)}/${encodeURIComponent(identity)}`
  const { data } = await api.post<Lease>(`${path}/acquire`, { editor_id })
  if (!data.owned) throw new Error(`${data.owner || "Another user"} is editing this document.`)
  try {
    return await action({ headers: { "X-Edit-Session": editor_id } })
  } finally {
    await api.post(`${path}/release`, { editor_id }).catch(() => undefined)
  }
}

/** One lease per mounted form, including separate tabs under the same login. */
export function useDocumentEditor(kind: string, identity: string, enabled: boolean, prepare?: () => Promise<unknown>) {
  const key = `${kind}/${identity}`
  const [state, setState] = useState<State | null>(null)
  const current = useRef<State | null>(null)
  const prepareRef = useRef(prepare)
  prepareRef.current = prepare
  useEffect(() => {
    if (!enabled || !identity) return
    const session = crypto.randomUUID()
    const endpoint = `/editing/${encodeURIComponent(kind)}/${encodeURIComponent(identity)}`
    let disposed = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const update = (lease: Lease | null, error = "") => {
      const next = { key, session, lease, error }
      current.current = next
      setState(next)
    }
    const release = () => api.post(`${endpoint}/release`, { editor_id: session }, { keepalive: true }).catch(() => undefined)
    const leavePage = () => {
      disposed = true
      clearTimeout(timer)
      update(null, "Editing session closed. Reload the document before editing again.")
      void release()
    }
    window.addEventListener("pagehide", leavePage)
    const renew = async () => {
      try {
        const { data } = await api.post<Lease>(`${endpoint}/renew`, { editor_id: session })
        if (disposed) return
        update(data)
        timer = setTimeout(renew, data.renew_after_seconds * 1000)
      } catch (error) {
        if (!disposed) update(null, error instanceof Error ? error.message : "Editing session lost.")
      }
    }
    update(null)
    void api.post<Lease>(`${endpoint}/acquire`, { editor_id: session }).then(async ({ data }) => {
      if (disposed) { if (data.owned) await release(); return }
      if (data.owned) {
        try { await prepareRef.current?.() } catch (error) { await release(); throw error }
        if (disposed) { await release(); return }
      }
      update(data)
      if (data.owned) timer = setTimeout(renew, data.renew_after_seconds * 1000)
    }).catch((error) => {
      if (!disposed) update(null, error instanceof Error ? error.message : "Unable to start editing.")
    })
    return () => {
      disposed = true
      clearTimeout(timer)
      window.removeEventListener("pagehide", leavePage)
      current.current = null
      void release()
    }
  }, [enabled, identity, key, kind])
  const active = state?.key === key ? state : null
  const owned = !enabled || Boolean(active?.lease?.owned && active.lease.expires_at && Date.parse(active.lease.expires_at) > Date.now())
  const options = (): RequestInit => {
    if (!enabled) return {}
    const live = current.current
    if (live?.key !== key || !live.lease?.owned || !live.lease.expires_at || Date.parse(live.lease.expires_at) <= Date.now()) {
      throw new Error("This editing session is not active. Keep your unsaved text and reload before editing again.")
    }
    return { headers: { "X-Edit-Session": live.session } }
  }
  return { owned, enabled, owner: active?.lease?.owner, error: active?.error, pending: enabled && !active?.lease && !active?.error, options }
}
