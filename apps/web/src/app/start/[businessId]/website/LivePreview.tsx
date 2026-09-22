'use client'

import { useEffect, useRef, useState } from 'react'
import { personalizationStatus } from './actions'

/**
 * The website itself, the moment the owner arrives.
 *
 * "Build my website" writes a real draft synchronously before this page is
 * reached, so there is something true to show immediately — and showing a
 * spinner over a site that already exists would be a lie told for the sake of
 * a loading animation. The frame is the actual published-preview renderer at
 * the actual draft, not a mock of one.
 *
 * Personalization continues behind it. That is a second, better draft rather
 * than a missing first one, so it is announced quietly and swapped in when it
 * lands. Polling stops the moment the job leaves the queue, and the frame is
 * never blocked on it: a personalization that fails or is superseded simply
 * leaves the site the owner is already looking at.
 */
export function LivePreview({
  businessId,
  src,
  initialStatus,
}: {
  businessId: string
  src: string
  initialStatus: string | null
}) {
  const running = (status: string | null) => status === 'pending' || status === 'running'
  const [status, setStatus] = useState(initialStatus)
  const [device, setDevice] = useState<'desktop' | 'phone'>('desktop')
  const [refreshed, setRefreshed] = useState(0)
  const frame = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    if (!running(status)) return
    let cancelled = false
    const timer = setInterval(async () => {
      const next = await personalizationStatus(businessId)
      if (cancelled) return
      if (!running(next)) {
        setStatus(next)
        clearInterval(timer)
        // Only a finished personalization changes what the frame should show.
        if (next === 'completed') setRefreshed((n) => n + 1)
      }
    }, 4000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [businessId, status])

  const note =
    status === 'completed'
      ? 'Locah finished writing your pages. This is the updated version.'
      : running(status)
        ? 'This is your site now. Locah is still writing your wording in the background — it will appear here on its own.'
        : status === 'superseded'
          ? 'Your own edits were kept, so the background rewrite was not applied.'
          : status === 'fallback_used'
            ? 'Locah could not reach the writing model, so your site uses your own words as written. Everything is editable.'
            : 'This is your draft. Only you can see it until you publish.'

  return (
    <div className="lp">
      <div className="lp-bar">
        <p className="lp-note" role="status">
          {running(status) ? <span className="lp-dot" aria-hidden="true" /> : null}
          {note}
        </p>
        <div className="lp-devices" role="group" aria-label="Preview size">
          <button
            type="button"
            className="lc-btn"
            aria-pressed={device === 'desktop'}
            onClick={() => setDevice('desktop')}
          >
            Desktop
          </button>
          <button
            type="button"
            className="lc-btn"
            aria-pressed={device === 'phone'}
            onClick={() => setDevice('phone')}
          >
            Phone
          </button>
        </div>
      </div>
      <div className={`lp-stage lp-stage--${device}`}>
        <iframe
          ref={frame}
          key={refreshed}
          src={src}
          title="Preview of your website"
          loading="eager"
          sandbox="allow-same-origin allow-scripts"
        />
      </div>
    </div>
  )
}
