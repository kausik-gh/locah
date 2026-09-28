'use client'

import Link from 'next/link'
import { useState, useTransition } from 'react'
import { setToolSection } from './site-actions'

export type SiteAction = { key: string; label: string; live: boolean; module: string; next_step: string | null }
export type ToolSection = { module: string; section_type: string | null; label: string; state: 'showing' | 'hidden' }

/**
 * What the business's tools put on its website (Founder §14–16): the things a
 * customer can do there right now — the same answer the Marketplace listing
 * uses — and the sections a tool adds when the design has nothing for it.
 * Nothing here is a setting that can make a button work; a tool that is not
 * set up says what is missing.
 */
export function ToolsOnSite({
  businessId,
  primaryLabel,
  actions,
  sections,
}: {
  businessId: string
  primaryLabel: string | null
  actions: SiteAction[]
  sections: ToolSection[]
}) {
  const [pending, start] = useTransition()
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const live = actions.filter((a) => a.live)
  const waiting = actions.filter((a) => !a.live)

  return (
    <div className="bos-works" style={{ marginBottom: '2rem' }}>
      <section className="bos-card" aria-labelledby="site-can-do">
        <div className="bos-card__head">
          <h2 id="site-can-do">What customers can do on your site</h2>
          {primaryLabel ? <span className="bos-state is-ready">Main button: {primaryLabel}</span> : null}
        </div>
        <p className="bos-hint">
          Your website and your Marketplace listing both offer exactly these. When you finish setting up a tool, its
          button appears — no rebuild.
        </p>
        {live.length > 0 ? (
          <ul className="bos-pills" aria-label="Live on your site">
            {live.map((a) => (
              <li key={a.key} className="bos-pill">
                {a.label}
              </li>
            ))}
          </ul>
        ) : (
          <p className="bos-hint">
            Nothing to buy, book or ask yet — visitors can call or message you. Set up a tool below to add more.
          </p>
        )}
        {waiting.length > 0 ? (
          <ul className="bos-mini-list" style={{ marginTop: '1rem' }} aria-label="Not on your site yet">
            {waiting.map((a) => (
              <li key={a.key}>
                <div>
                  <strong>{a.label}</strong>
                  <p>Not yet: {a.next_step}</p>
                </div>
                <Link href={`/b/${businessId}/modules`}>Finish setup →</Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {sections.length > 0 ? (
        <section className="bos-card" aria-labelledby="site-tool-sections">
          <h2 id="site-tool-sections">Sections your tools add</h2>
          <p className="bos-hint">
            Your home page had nothing showing these, so your tools add them above your contact details. Hide any you
            would rather not show; your own design is never changed.
          </p>
          <ul className="bos-mini-list">
            {sections.map((s) => (
              <li key={s.module}>
                <div>
                  <strong>{s.label}</strong>
                  <p>{s.state === 'showing' ? 'Showing on your home page' : 'Hidden'}</p>
                </div>
                <label className="bos-toggle">
                  <input
                    type="checkbox"
                    checked={s.state === 'showing'}
                    disabled={pending}
                    aria-label={`Show ${s.label.toLowerCase()} on your website`}
                    onChange={(e) => {
                      const show = e.currentTarget.checked
                      setError(null)
                      setStatus(null)
                      start(async () => {
                        const r = await setToolSection(businessId, s.module, !show)
                        if (r.ok) setStatus(show ? 'Showing on your site.' : 'Hidden from your site.')
                        else setError(r.message)
                      })
                    }}
                  />
                  <span className="bos-toggle__track" aria-hidden="true" />
                  <span>{s.state === 'showing' ? 'Showing' : 'Hidden'}</span>
                </label>
              </li>
            ))}
          </ul>
          <p className={`bos-status ${error ? 'bos-error' : ''}`} role="status">
            {error || status || ''}
          </p>
        </section>
      ) : null}
    </div>
  )
}
