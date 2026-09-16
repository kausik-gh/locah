'use client'

/**
 * Last-resort boundary — catches errors thrown in the root layout itself,
 * where `error.tsx` cannot reach. Must render its own <html>/<body>.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: 'Georgia, "Times New Roman", serif',
          background: 'linear-gradient(160deg, #f7f3eb 0%, #e8eef2 100%)',
          color: '#1c2430',
        }}
      >
        <div
          style={{
            display: 'grid',
            placeItems: 'center',
            minHeight: '100vh',
            padding: '2rem',
          }}
        >
          <div style={{ maxWidth: '32rem', textAlign: 'center' }}>
            <h1 style={{ fontSize: '1.6rem', marginBottom: '0.5rem' }}>The Workspace failed to load</h1>
            <p style={{ opacity: 0.85, lineHeight: 1.6 }}>
              Please reload the page. If this keeps happening, contact support.
            </p>
            <button
              type="button"
              onClick={() => reset()}
              style={{
                marginTop: '1rem',
                padding: '0.55rem 1.1rem',
                borderRadius: '6px',
                border: '1px solid rgba(28,36,48,0.25)',
                background: 'rgba(28,36,48,0.9)',
                color: '#f7f3eb',
                font: 'inherit',
                cursor: 'pointer',
              }}
            >
              Reload
            </button>
            {error.digest ? (
              <p style={{ opacity: 0.5, fontSize: '0.8rem', marginTop: '1rem' }}>
                Reference: {error.digest}
              </p>
            ) : null}
          </div>
        </div>
      </body>
    </html>
  )
}
