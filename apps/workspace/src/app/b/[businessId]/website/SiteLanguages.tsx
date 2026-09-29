'use client'

import { useState, useTransition } from 'react'
import { setSiteLanguages } from './site-actions'

const LANGS = [
  { key: 'en', name: 'English', own: 'English' },
  { key: 'ta', name: 'Tamil', own: 'தமிழ்' },
  { key: 'hi', name: 'Hindi', own: 'हिंदी' },
] as const

/**
 * Which languages the site's own words come in (P1-10E6): buttons, the basket,
 * checkout, bookings, and the pages customers are sent — bills, payment links,
 * tracking. What the owner wrote stays exactly as written. With more than one,
 * visitors get a switch at the top of every page.
 */
export function SiteLanguages({ businessId, initial }: { businessId: string; initial: string[] }) {
  const [on, setOn] = useState<string[]>(initial.length ? initial : ['en'])
  const [first, setFirst] = useState(initial[0] ?? 'en')
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const [pending, start] = useTransition()
  const changed = on.join() !== initial.join() || first !== (initial[0] ?? 'en')

  const toggle = (key: string) => {
    setMsg(null)
    const next = on.includes(key) ? on.filter((k) => k !== key) : [...on, key]
    if (!next.length) return setMsg({ text: 'Keep at least one language.', bad: true })
    setOn(next)
    if (!next.includes(first)) setFirst(next[0])
  }
  const save = () =>
    start(async () => {
      const ordered = [first, ...LANGS.map((l) => l.key).filter((k) => k !== first && on.includes(k))]
      const r = await setSiteLanguages(businessId, ordered)
      setMsg(r.ok ? { text: 'Saved. Your live site uses these now.', bad: false } : { text: r.message, bad: true })
    })

  return (
    <section className="bos-card" aria-labelledby="site-langs-h" style={{ marginBottom: '2rem' }}>
      <div className="bos-card__head">
        <h2 id="site-langs-h">Languages on your website</h2>
      </div>
      <p className="bos-hint">
        Buttons, the basket, checkout, bookings and the pages customers are sent — bills, payment links, tracking — come
        in each language you tick. What you wrote on your pages stays as you wrote it. Visitors switch language at the
        top of the page.
      </p>
      <fieldset className="bos-choices" style={{ border: 0, padding: 0, margin: '0.6rem 0' }}>
        <legend className="sr-only">Languages</legend>
        {LANGS.map((l) => (
          <label key={l.key} className="bos-choice">
            <input type="checkbox" name={`site-lang-${l.key}`} checked={on.includes(l.key)} onChange={() => toggle(l.key)} />
            <span lang={l.key}>{l.own}</span>{l.own !== l.name ? ` · ${l.name}` : null}
          </label>
        ))}
      </fieldset>
      {on.length > 1 ? (
        <label style={{ display: 'block', maxWidth: '20rem' }}>
          <span className="bos-label">Visitors see first</span>
          <select name="site-lang-first" value={first} onChange={(e) => setFirst(e.target.value)}>
            {LANGS.filter((l) => on.includes(l.key)).map((l) => <option key={l.key} value={l.key}>{l.own}</option>)}
          </select>
        </label>
      ) : null}
      <p style={{ marginTop: '0.8rem' }}>
        <button type="button" onClick={save} disabled={pending || !changed}>{pending ? 'Saving…' : 'Save languages'}</button>
      </p>
      <p className="bos-hint">The Tamil and Hindi wording is new — tell us if anything reads wrong.</p>
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
    </section>
  )
}
