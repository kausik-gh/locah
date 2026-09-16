'use client'

import { useEffect, useState } from 'react'

/**
 * Cross-origin hand-off to the Workspace app.
 *
 * Done from the client on purpose: a server-action `redirect()` to another
 * origin is not followed by the Next client router. The link is always
 * rendered, so this works with or without JS.
 */
export function HandOff({ href }: { href: string }) {
  const [auto, setAuto] = useState(true)

  useEffect(() => {
    if (!auto) return
    const t = setTimeout(() => {
      window.location.href = href
    }, 2500)
    return () => clearTimeout(t)
  }, [auto, href])

  return (
    <div style={{ display: 'flex', gap: '0.9rem', flexWrap: 'wrap', alignItems: 'center' }}>
      <a
        href={href}
        onClick={() => setAuto(false)}
        style={{
          display: 'inline-block',
          padding: '0.75rem 1.5rem',
          borderRadius: '8px',
          background: '#1c5f57',
          color: '#fff',
          textDecoration: 'none',
          fontWeight: 600,
          fontFamily: 'system-ui, sans-serif',
          fontSize: '0.98rem',
        }}
      >
        Open my Workspace →
      </a>
      {auto ? (
        <button
          type="button"
          onClick={() => setAuto(false)}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            color: '#4c5967',
            fontFamily: 'system-ui, sans-serif',
            fontSize: '0.85rem',
            cursor: 'pointer',
            textDecoration: 'underline',
          }}
        >
          taking you there automatically — stay here instead
        </button>
      ) : null}
    </div>
  )
}
