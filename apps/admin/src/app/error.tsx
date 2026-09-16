'use client'

/**
 * Route-level backstop for the Admin app. Pages surface auth/permission
 * failures themselves via `apiTry` + `AdminNotice`; this only catches an
 * unhandled throw or a render fault so the fallback is readable.
 */
export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div style={{ padding: '2rem', color: '#e8eef4', fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <div
        style={{
          maxWidth: '34rem',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.14)',
          borderRadius: '10px',
          padding: '1.6rem',
        }}
      >
        <h1 style={{ fontSize: '1.4rem', marginTop: 0 }}>Something went wrong</h1>
        <p style={{ opacity: 0.85, lineHeight: 1.6 }}>
          This page failed to render. Try again, or return to the Admin home.
        </p>
        <button
          type="button"
          onClick={() => reset()}
          style={{
            marginTop: '0.75rem',
            padding: '0.5rem 1rem',
            borderRadius: '6px',
            border: '1px solid rgba(255,255,255,0.25)',
            background: '#2d6cdf',
            color: '#fff',
            font: 'inherit',
            cursor: 'pointer',
          }}
        >
          Try again
        </button>
        {error.digest ? (
          <p style={{ opacity: 0.5, fontSize: '0.8rem', marginTop: '1rem' }}>
            Reference: {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  )
}
