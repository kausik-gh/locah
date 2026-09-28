'use client'

import { useMemo, useState, useTransition } from 'react'
import { saveKind, saveOrgShape, saveTraits } from './actions'

export type Trait = { key: string; label: string; on: boolean; default: boolean; source: string | null }
export type TraitGroup = { key: string; label: string; traits: Trait[] }
export type Kind = { category_key: string; category_label: string; key: string; label: string }

/**
 * "How your business works" (Capability Universe §4.3: traits start from the
 * kind of business, are confirmed by the owner, editable later in Settings).
 * Every control is a plain sentence; the owner never sees a key.
 */
export function BusinessWorksEditor({
  businessId,
  kindLabel,
  groupLabel,
  orgShape,
  orgShapes,
  groups,
  kinds,
}: {
  businessId: string
  kindLabel: string | null
  groupLabel: string | null
  orgShape: string
  orgShapes: { key: string; label: string }[]
  groups: TraitGroup[]
  kinds: Kind[]
}) {
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [picking, setPicking] = useState(!kindLabel)
  const [query, setQuery] = useState('')
  const [local, setLocal] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(groups.flatMap((g) => g.traits.map((t) => [t.key, t.on]))),
  )

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return kinds
      .filter((k) => k.label.toLowerCase().includes(q) || k.category_label.toLowerCase().includes(q))
      .slice(0, 8)
  }, [query, kinds])

  const run = (fn: () => Promise<{ ok: boolean; message?: string }>, done: string) => {
    setError(null)
    setSaved(null)
    start(async () => {
      const r = await fn()
      if (r.ok) setSaved(done)
      else setError(('message' in r && r.message) || 'That did not save.')
    })
  }

  const toggle = (key: string) => {
    const next = !local[key]
    setLocal((s) => ({ ...s, [key]: next }))
    run(() => saveTraits(businessId, { [key]: next }), 'Saved. Your recommended tools have been updated.')
  }

  return (
    <div className="bos-works">
      <section className="bos-card" aria-labelledby="kind-h">
        <div className="bos-card__head">
          <h2 id="kind-h">What kind of business</h2>
          {kindLabel && !picking ? (
            <button type="button" className="btn-quiet" onClick={() => setPicking(true)}>Change</button>
          ) : null}
        </div>
        {kindLabel && !picking ? (
          <p className="bos-kind">
            <strong>{kindLabel}</strong>
            {groupLabel ? <span> · {groupLabel}</span> : null}
          </p>
        ) : (
          <div className="bos-picker">
            <label htmlFor="kind-search" className="bos-label">Search, for example “meat shop”, “dental clinic”, “tiffin service”</label>
            <input
              id="kind-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What kind of business is it?"
              autoComplete="off"
            />
            {matches.length > 0 ? (
              <ul className="bos-picker__list" role="listbox" aria-label="Matching kinds of business">
                {matches.map((k) => (
                  <li key={k.key}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={false}
                      disabled={pending}
                      onClick={() => {
                        setPicking(false)
                        run(() => saveKind(businessId, k.category_key, k.key === k.category_key ? null : k.key),
                          `Now set up as ${k.label}. Default ways of working were updated; your own choices were kept.`)
                      }}
                    >
                      <span>{k.label}</span>
                      <small>{k.category_label}</small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : query.trim().length >= 2 ? (
              <p className="bos-hint">No match yet — try another word.</p>
            ) : null}
            {kindLabel ? (
              <button type="button" className="btn-quiet" onClick={() => setPicking(false)}>Keep {kindLabel}</button>
            ) : null}
          </div>
        )}
      </section>

      <section className="bos-card" aria-labelledby="shape-h">
        <h2 id="shape-h">How you are organised</h2>
        <p className="bos-hint">This decides which team tools and roles LOCAH shows you — not which modules you can use.</p>
        <div className="bos-choices" role="radiogroup" aria-labelledby="shape-h">
          {orgShapes.map((s) => (
            <label key={s.key} className={`bos-choice${orgShape === s.key ? ' is-on' : ''}`}>
              <input
                type="radio"
                name="org_shape"
                value={s.key}
                defaultChecked={orgShape === s.key}
                disabled={pending}
                onChange={() => run(() => saveOrgShape(businessId, s.key), 'Saved.')}
              />
              {s.label}
            </label>
          ))}
        </div>
      </section>

      <section className="bos-card" aria-labelledby="traits-h">
        <h2 id="traits-h">How your business works</h2>
        <p className="bos-hint">
          LOCAH started from what {kindLabel ? `a ${kindLabel.toLowerCase()}` : 'businesses like yours'} usually does.
          Switch anything that is not true for you — recommendations follow what you choose.
        </p>
        <div className="bos-trait-groups">
          {groups.map((g) => (
            <fieldset key={g.key} className="bos-trait-group">
              <legend>{g.label}</legend>
              {g.traits.map((t) => (
                <label key={t.key} className="bos-toggle">
                  <input
                    type="checkbox"
                    checked={!!local[t.key]}
                    disabled={pending}
                    onChange={() => toggle(t.key)}
                  />
                  <span className="bos-toggle__track" aria-hidden />
                  <span className="bos-toggle__text">{t.label}</span>
                  {t.source === 'owner' ? <small className="bos-tag">your choice</small> : null}
                </label>
              ))}
            </fieldset>
          ))}
        </div>
      </section>

      <p className="bos-status" role="status" aria-live="polite">
        {pending ? 'Saving…' : error ? <span className="bos-error">{error}</span> : saved}
      </p>
    </div>
  )
}
