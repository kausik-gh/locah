'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { previewSegment, saveSegment, type Preview, type Rule } from './segment-actions'

export type RuleKind = { kind: string; label: string; fields: string[] }

const FIELD_LABEL: Record<string, string> = {
  offering_id: 'Item',
  times: 'At least (times)',
  days: 'In the last (days)',
  amount: 'Amount (₹)',
  from_days: 'Between (days ago)',
  to_days: 'and (days ago)',
  tag: 'Tag',
}
const DEFAULTS: Record<string, Rule> = {
  bought: { times: 2, days: 60 },
  spent: { amount: 5000, days: 90 },
  lapsed: { days: 90 },
  new: { days: 30 },
  booked: { times: 3, days: 90 },
  membership_ended: { from_days: 15, to_days: 60 },
  owes: {},
  tag: {},
}

/** Build a segment from rules that must all hold; see who is in it before saving (CR-04). */
export function SegmentBuilder({ businessId, kinds, items, tags, canSave }: {
  businessId: string
  kinds: RuleKind[]
  items: { id: string; title: string }[]
  tags: string[]
  canSave: boolean
}) {
  const router = useRouter()
  const first = kinds[0]?.kind ?? 'new'
  const blank = (kind: string): Rule => ({
    kind,
    ...DEFAULTS[kind],
    ...(kind === 'bought' && items[0] ? { offering_id: items[0].id } : {}),
    ...(kind === 'tag' && tags[0] ? { tag: tags[0] } : {}),
  })
  const [name, setName] = useState('')
  const [rules, setRules] = useState<Rule[]>([blank(first)])
  const [preview, setPreview] = useState<Preview | null>(null)
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)

  const set = (i: number, patch: Rule) => {
    setPreview(null)
    setRules((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  }
  const see = () => {
    setMsg(null)
    start(async () => {
      const r = await previewSegment(businessId, rules)
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      setPreview(r.data ?? null)
    })
  }
  const save = () => {
    setMsg(null)
    if (!name.trim()) return setMsg({ text: 'Name the segment, for example “Regulars”.', bad: true })
    start(async () => {
      const r = await saveSegment(businessId, name.trim(), rules)
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      setMsg({ text: `Saved “${name.trim()}”.`, bad: false })
      setName('')
      setRules([blank(first)])
      setPreview(null)
      router.refresh()
    })
  }

  return (
    <section className="bos-card" aria-labelledby="seg-new-h" style={{ marginTop: '1.4rem' }}>
      <h2 id="seg-new-h">Build a segment</h2>
      <p className="bos-hint">Customers who match every rule.</p>
      {rules.map((r, i) => {
        const kind = kinds.find((k) => k.kind === r.kind)
        return (
          <div key={i} className="bos-seg-rule">
            <label>
              <span className="bos-label">Rule {i + 1}</span>
              <select name={`rule-${i}-kind`} value={String(r.kind)} onChange={(e) => {
                setPreview(null)
                setRules((rs) => rs.map((x, j) => (j === i ? blank(e.target.value) : x)))
              }}>
                {kinds.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
              </select>
            </label>
            {(kind?.fields ?? []).map((f) => (
              <label key={f}>
                <span className="bos-label">{FIELD_LABEL[f] ?? f}</span>
                {f === 'offering_id' ? (
                  <select name={`rule-${i}-${f}`} value={String(r[f] ?? '')} onChange={(e) => set(i, { [f]: e.target.value })}>
                    {items.map((it) => <option key={it.id} value={it.id}>{it.title}</option>)}
                  </select>
                ) : f === 'tag' ? (
                  <input name={`rule-${i}-${f}`} list="seg-tags" value={String(r[f] ?? '')} onChange={(e) => set(i, { [f]: e.target.value })} />
                ) : (
                  <input name={`rule-${i}-${f}`} inputMode="numeric" value={String(r[f] ?? '')} onChange={(e) => set(i, { [f]: e.target.value })} />
                )}
              </label>
            ))}
            {rules.length > 1 ? (
              <button type="button" className="btn-quiet" onClick={() => { setPreview(null); setRules((rs) => rs.filter((_, j) => j !== i)) }}>
                Remove
              </button>
            ) : <span />}
          </div>
        )
      })}
      <datalist id="seg-tags">{tags.map((t) => <option key={t} value={t} />)}</datalist>
      <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginTop: '.4rem' }}>
        {rules.length < 6 ? (
          <button type="button" className="btn-ghost" onClick={() => { setPreview(null); setRules((rs) => [...rs, blank(first)]) }}>Add a rule</button>
        ) : null}
        <button type="button" onClick={see} disabled={pending}>{pending ? 'Counting…' : 'See who is in it'}</button>
      </div>
      {preview ? (
        <div role="status" aria-live="polite">
          <p className="bos-seg-count">{preview.count === 1 ? '1 customer' : `${preview.count} customers`}</p>
          <p className="bos-hint">
            {preview.rule_words.join(' · ')}.{' '}
            {preview.whatsapp_offers} said yes to offers on WhatsApp — only they can be sent one.
          </p>
          {preview.members.length ? (
            <ul className="bos-seg-list">
              {preview.members.map((m) => (
                <li key={m.id}><Link href={`/b/${businessId}/customers/${m.id}`}>{m.display_name}</Link><span className="bos-hint">{m.phone ?? ''}</span></li>
              ))}
            </ul>
          ) : null}
          {preview.count > preview.members.length ? <p className="bos-hint">Showing the first {preview.members.length}. Save it to see everyone.</p> : null}
        </div>
      ) : null}
      {canSave ? (
        <div className="bos-form-grid" style={{ marginTop: '.8rem', alignItems: 'end' }}>
          <label>
            <span className="bos-label">Segment name</span>
            <input name="segment-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Cake regulars" />
          </label>
          <div><button type="button" onClick={save} disabled={pending}>Save segment</button></div>
        </div>
      ) : null}
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
    </section>
  )
}
