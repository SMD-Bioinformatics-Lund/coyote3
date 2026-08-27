export function AppLoader({ label = "Loading" }: { label?: string }) {
  return <GlobalLoadingIndicator label={label} />
}

export function GlobalLoadingIndicator({ label = "Loading" }: { label?: string }) {
  return (
    <div className="global-loader" role="status" aria-live="polite" aria-label={label}>
      <div className="global-loader-window">
        <div className="app-loader-material" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <span className="app-loader-label">Loading</span>
      </div>
    </div>
  )
}
