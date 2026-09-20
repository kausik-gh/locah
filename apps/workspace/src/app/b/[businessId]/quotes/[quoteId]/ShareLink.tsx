'use client'

import { useState } from 'react'
import { LocalTime } from '@/components/LocalTime'

/**
 * The link the customer opens.
 *
 * The token is the customer's entire credential for this quote, so the useful
 * thing to hand the owner is the finished address rather than the token — there
 * is nothing they need to assemble, and nothing to get wrong when they paste it
 * into WhatsApp.
 *
 * Copying is offered but never assumed: `navigator.clipboard` needs a secure
 * context and a permission that can be refused, so the address stays visible and
 * selectable whether or not the button works.
 *
 * The expiry date goes through `LocalTime` rather than being formatted inline.
 * A client component still renders once on the server, and `toLocaleDateString`
 * answers with the server's locale there and the browser's here — which React
 * sees as a hydration mismatch and repairs by throwing away the server HTML.
 */
export function ShareLink({ url, expiresAt }: { url: string; expiresAt?: string | null }) {
  const [copied, setCopied] = useState(false)
  const [failed, setFailed] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setFailed(false)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setFailed(true)
    }
  }

  return (
    <div style={{ display: 'grid', gap: '0.5rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          readOnly
          value={url}
          onFocus={(e) => e.currentTarget.select()}
          aria-label="Customer link for this quote"
          style={{ flex: '1 1 20rem', minWidth: 0, fontFamily: 'var(--font-mono, monospace)', fontSize: '0.85rem' }}
        />
        <button type="button" className="btn btn-ghost" onClick={copy}>
          {copied ? 'Copied' : 'Copy link'}
        </button>
        <a href={url} target="_blank" rel="noreferrer" className="btn btn-ghost">
          Open ↗
        </a>
      </div>
      {failed ? (
        <span style={{ fontSize: '0.82rem', color: 'var(--color-muted)' }}>
          Copying was blocked by the browser — select the address above and copy it by hand.
        </span>
      ) : null}
      {expiresAt ? (
        <span style={{ fontSize: '0.82rem', color: 'var(--color-muted)' }}>
          The link stops working on <LocalTime value={expiresAt} mode="date" />.
        </span>
      ) : null}
    </div>
  )
}
