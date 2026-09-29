'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { saveStages, type StageEntity, type StageRow } from '@/lib/stage-actions'

export type StageSet = {
  entity: StageEntity
  version: number
  stages: { key: string; label: string; status: string; custom: boolean; needs_note: boolean }[]
  open: string[]
}

const MAX_STEPS = 20

/**
 * One module's stages (P2-01): its own statuses, which can be renamed but not
 * removed, and the business's steps inside the open ones — added, renamed,
 * reordered, removed, or marked as needing a note.
 */
export function StagesEditor({ businessId, title, hint, set, canEdit }: {
  businessId: string; title: string; hint: string; set: StageSet; canEdit: boolean
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [rows, setRows] = useState<StageRow[]>(set.stages.map((s) => ({ ...s })))
  const [adding, setAdding] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const cores = rows.filter((r) => !r.custom)
  const steps = rows.filter((r) => r.custom).length
  const dirty = JSON.stringify(rows) !== JSON.stringify(set.stages)

  const edit = (i: number, patch: Partial<StageRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const drop = (i: number) => setRows(rows.filter((_, j) => j !== i))
  const shift = (i: number, by: -1 | 1) => {
    const j = i + by
    if (!rows[j] || !rows[j].custom || rows[j].status !== rows[i].status) return
    const next = [...rows]
    ;[next[i], next[j]] = [next[j], next[i]]
    setRows(next)
  }
  const add = (status: string) => {
    const label = (adding[status] || '').trim()
    if (!label) return
    let at = rows.length
    rows.forEach((r, i) => { if (r.status === status) at = i + 1 })
    setRows([...rows.slice(0, at), { label, status, custom: true, needs_note: false }, ...rows.slice(at)])
    setAdding({ ...adding, [status]: '' })
  }
  const save = () =>
    start(async () => {
      setMsg(null)
      const r = await saveStages(businessId, set.entity,
        rows.map((x) => ({ key: x.key, label: x.label, status: x.status, needs_note: Boolean(x.needs_note) })))
      setMsg(r.ok ? { text: 'Saved. New steps show on each record from now.' } : { text: r.message, bad: true })
      if (r.ok) router.refresh()
    })

  return (
    <section className="bos-card bos-stages" aria-labelledby={`stages-${set.entity}`}>
      <div className="bos-card__head">
        <h2 id={`stages-${set.entity}`}>{title}</h2>
        <span className="bos-hint" style={{ margin: 0 }}>{steps} of {MAX_STEPS} steps</span>
      </div>
      <p className="bos-hint">{hint}</p>
      <ol className="bos-stages__list">
        {cores.map((core) => {
          const ci = rows.indexOf(core)
          const mine = rows.map((r, i) => [r, i] as const).filter(([r]) => r.custom && r.status === core.status)
          const open = set.open.includes(core.status)
          return (
            <li key={core.status} className="bos-stages__status">
              <div className="bos-stages__row">
                <input aria-label={`Name for ${core.status}`} value={core.label} maxLength={40} disabled={!canEdit}
                  onChange={(e) => edit(ci, { label: e.target.value })} />
                <label className="bos-stages__note">
                  <input type="checkbox" checked={Boolean(core.needs_note)} disabled={!canEdit}
                    onChange={(e) => edit(ci, { needs_note: e.target.checked })} /> Needs a note
                </label>
              </div>
              {mine.length ? (
                <ol className="bos-stages__steps">
                  {mine.map(([step, i], n) => (
                    <li key={step.key || `new-${i}`} className="bos-stages__row">
                      <input aria-label="Step name" value={step.label} maxLength={40} disabled={!canEdit}
                        onChange={(e) => edit(i, { label: e.target.value })} />
                      <label className="bos-stages__note">
                        <input type="checkbox" checked={Boolean(step.needs_note)} disabled={!canEdit}
                          onChange={(e) => edit(i, { needs_note: e.target.checked })} /> Needs a note
                      </label>
                      {canEdit ? (
                        <span className="bos-stages__tools">
                          <button type="button" className="btn-ghost" aria-label={`Move ${step.label} up`}
                            disabled={n === 0} onClick={() => shift(i, -1)}>↑</button>
                          <button type="button" className="btn-ghost" aria-label={`Move ${step.label} down`}
                            disabled={n === mine.length - 1} onClick={() => shift(i, 1)}>↓</button>
                          <button type="button" className="btn-ghost" onClick={() => drop(i)}>Remove</button>
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ol>
              ) : null}
              {open && canEdit ? (
                <div className="bos-stages__add">
                  <input aria-label={`New step inside ${core.label}`} placeholder={`A step inside “${core.label}”`}
                    value={adding[core.status] || ''} maxLength={40}
                    onChange={(e) => setAdding({ ...adding, [core.status]: e.target.value })}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(core.status) } }} />
                  <button type="button" className="btn-ghost" disabled={steps >= MAX_STEPS || !(adding[core.status] || '').trim()}
                    onClick={() => add(core.status)}>Add step</button>
                </div>
              ) : null}
            </li>
          )
        })}
      </ol>
      {canEdit ? (
        <div className="bos-inv-buttons">
          <button type="button" onClick={save} disabled={pending || !dirty}>{pending ? 'Saving…' : 'Save stages'}</button>
          {dirty ? <button type="button" className="btn-ghost" onClick={() => setRows(set.stages.map((s) => ({ ...s })))}>Undo changes</button> : null}
        </div>
      ) : (
        <p className="bos-hint">Only people who can change settings can edit these.</p>
      )}
      {msg ? <p role="status" className={msg.bad ? 'bos-inv-warn' : 'bos-hint'}>{msg.text}</p> : null}
    </section>
  )
}
