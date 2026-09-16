'use client'

/**
 * Route-level error backstop for the Workspace app.
 *
 * Pages should surface gate failures themselves via `apiTry` + `GateNotice`
 * (see components/ModuleState.tsx). This boundary only catches what a page
 * missed — an unhandled throw from `apiGet`, a server-action error, a render
 * fault — so the viewer gets a readable, recoverable screen instead of the
 * framework's default. It is a safety net, not the primary error UX.
 */
export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div
      style={{
        display: 'grid',
        placeItems: 'center',
        minHeight: '60vh',
        fontFamily: 'Georgia, "Times New Roman", serif',
        color: '#1c2430',
        padding: '2rem',
      }}
    >
      <div
        style={{
          maxWidth: '34rem',
          background: 'rgba(255,255,255,0.65)',
          border: '1px solid rgba(28,36,48,0.14)',
          borderRadius: '10px',
          padding: '1.75rem',
        }}
      >
        <h1 style={{ fontSize: '1.5rem', margin: '0 0 0.5rem' }}>Something went wrong on this page</h1>
        <p style={{ opacity: 0.85, lineHeight: 1.6 }}>
          This is usually temporary. Try again, or go back to your Workspace home. Your data has not
          been affected.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.1rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: '0.55rem 1rem',
              borderRadius: '6px',
              border: '1px solid rgba(28,36,48,0.25)',
              background: 'rgba(28,36,48,0.9)',
              color: '#f7f3eb',
              font: 'inherit',
              cursor: 'pointer',
            }}
          >
            Try again
          </button>
          <a href="/" style={{ alignSelf: 'center', color: '#1c2430' }}>
            Workspace home
          </a>
        </div>
        {error.digest ? (
          <p style={{ opacity: 0.5, fontSize: '0.8rem', marginTop: '1rem' }}>
            Reference: {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  )
}
