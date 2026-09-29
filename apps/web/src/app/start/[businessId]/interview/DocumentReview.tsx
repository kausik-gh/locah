'use client'

import { useState } from 'react'
import type { DocumentRead } from '@platform/contracts'

/** How one line is keyed when the owner accepts it (matches the API's line_key). */
export const lineKey = (group: string, item: string) => `${group}::${item}`

const KIND: Record<DocumentRead['kind'], string> = {
  menu: 'menu',
  catalogue: 'catalogue',
  price_list: 'price list',
  brochure: 'brochure',
  other: 'file',
}

/**
 * What LOCAH read from the owner's menu / catalogue — for them to check.
 *
 * Nothing reaches the website until the owner presses "Add". Lines LOCAH read
 * clearly start ticked; lines it could not read clearly start unticked and
 * say so, so a smudged price is never published on a guess.
 */
export function DocumentReview({
  doc,
  busy,
  onApply,
}: {
  doc: DocumentRead
  busy: boolean
  onApply: (accept: string[]) => void
}) {
  // Keyed by the parent on asset + status, so a fresh reading starts fresh.
  const [picked, setPicked] = useState<Set<string>>(
    () => new Set(doc.groups.flatMap((g) => g.items.filter((i) => i.confidence === 'high').map((i) => lineKey(g.name, i.name)))),
  )
  const kind = KIND[doc.kind]

  if (doc.status === 'reading') {
    return (
      <div className="ti-staged ti-doc" role="status">
        <p>Reading your {kind}… you can keep talking meanwhile.</p>
      </div>
    )
  }
  if (doc.status === 'failed') {
    return (
      <div className="ti-staged ti-doc" role="alert">
        <p>{doc.reason || `LOCAH couldn’t read that ${kind}.`}</p>
      </div>
    )
  }
  if (doc.status !== 'ready') return null
  const toggle = (key: string) =>
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const unclear = doc.groups.some((g) => g.items.some((i) => i.confidence === 'low'))

  return (
    <div className="ti-staged ti-doc" role="group" aria-label={`Items read from your ${kind}`}>
      <p>
        From your {kind}, I found these. Untick anything that’s wrong.
        {unclear ? ' Lines I couldn’t read clearly are unticked — check them first.' : ''}
      </p>
      <div className="ti-doc__groups">
        {doc.groups.map((g) => (
          <fieldset key={g.name} className="ti-doc__group">
            <legend>{g.name}</legend>
            {g.items.map((i) => {
              const key = lineKey(g.name, i.name)
              const detail = [i.variant, i.price ? `${i.price}${i.unit ? ` / ${i.unit}` : ''}` : i.unit, i.attributes]
                .filter(Boolean)
                .join(' · ')
              return (
                <label key={key} className={i.confidence === 'low' ? 'ti-doc__line ti-doc__line--check' : 'ti-doc__line'}>
                  <input type="checkbox" checked={picked.has(key)} onChange={() => toggle(key)} disabled={busy} />
                  <span>
                    <strong>{i.name}</strong>
                    {detail ? <small>{detail}</small> : null}
                    {i.confidence === 'low' ? <em>Couldn’t read this clearly</em> : null}
                  </span>
                </label>
              )
            })}
          </fieldset>
        ))}
      </div>
      {Object.keys(doc.facts).length ? (
        <p className="ti-doc__facts">
          It also shows {Object.entries(doc.facts).map(([k, v]) => `${k}: ${v}`).join(', ')} — tell me if you’d like that on your website.
        </p>
      ) : null}
      <div>
        <button type="button" className="lc-btn lc-btn--sm lc-btn--primary" disabled={busy || picked.size === 0} onClick={() => onApply([...picked])}>
          Add {picked.size} to my {doc.kind === 'menu' ? 'menu' : 'list'}
        </button>
      </div>
    </div>
  )
}
