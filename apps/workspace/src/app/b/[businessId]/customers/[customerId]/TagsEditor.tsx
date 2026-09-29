'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { saveTags } from './tag-actions'

/** Tags on one customer (CR-03): add from what the business already uses, or a new one; remove with ×. */
export function TagsEditor({ businessId, customerId, tags, version, known, canChange }: {
  businessId: string
  customerId: string
  tags: string[]
  version: number
  known: string[]
  canChange: boolean
}) {
  const router = useRouter()
  const [draft, setDraft] = useState('')
  const [current, setCurrent] = useState(tags)
  const [ver, setVer] = useState(version)
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const commit = (next: string[]) => {
    setError(null)
    start(async () => {
      const r = await saveTags(businessId, customerId, next, ver)
      if (!r.ok) return setError(r.message)
      setCurrent(r.data?.tags ?? next)
      if (r.data?.version) setVer(r.data.version)
      setDraft('')
      router.refresh()
    })
  }
  const add = () => {
    const t = draft.split(/\s+/).join(' ').trim().toLowerCase()
    if (!t) return
    if (current.includes(t)) return setDraft('')
    commit([...current, t])
  }

  return (
    <section className="bos-card bos-tags" aria-labelledby="tags-h">
      <h2 id="tags-h">Tags</h2>
      {current.length ? (
        <ul className="bos-tags__list">
          {current.map((t) => (
            <li key={t} className="bos-tag">
              {t}
              {canChange ? (
                <button type="button" aria-label={`Remove tag ${t}`} disabled={pending}
                  onClick={() => commit(current.filter((x) => x !== t))}>×</button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="bos-hint">No tags yet. Tags group customers — “regular”, “wholesale”, “wedding order”.</p>
      )}
      {canChange ? (
        <div className="bos-tags__add">
          <input aria-label="New tag" list="known-tags" value={draft} maxLength={64} placeholder="Add a tag"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
          <datalist id="known-tags">
            {known.filter((k) => !current.includes(k)).map((k) => <option key={k} value={k} />)}
          </datalist>
          <button type="button" className="btn-ghost" onClick={add} disabled={pending}>{pending ? 'Saving…' : 'Add tag'}</button>
        </div>
      ) : null}
      <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">{error ?? ''}</p>
    </section>
  )
}
