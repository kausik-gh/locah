'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { moveStage, type StageEntity } from '@/lib/stage-actions'
import { useWsWords } from '@/components/WsWords'
import { LocalTime } from '@/components/LocalTime'

export type Stage = { key: string; label: string; status: string; custom: boolean; needs_note: boolean }
export type StageWhere = {
  stage: Stage
  moves: Stage[]
  path: Stage[]
  has_steps: boolean
  version: number
  history: { from: string | null; to: string; note: string | null; at: string | null }[]
}

/**
 * A record's place among the business's own steps (P2-01, Capability Universe
 * §24 #10): the steps of its current status, the next ones it can move to, and
 * what happened when. Moves between the module's statuses keep their own
 * buttons (Accept, Start preparing…); this adds the business's steps between.
 */
export function StageTrack({ businessId, entity, recordId, where }: {
  businessId: string; entity: StageEntity; recordId: string; where: StageWhere
}) {
  const t = useWsWords()
  const router = useRouter()
  const [pending, start] = useTransition()
  const [asking, setAsking] = useState<Stage | null>(null)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const now = where.path.findIndex((s) => s.key === where.stage.key)
  // The business's own steps, and a step back to the status itself, are moved here.
  const nexts = where.moves.filter((m) => m.custom || m.status === where.stage.status)

  const go = (to: Stage, withNote: string) =>
    start(async () => {
      setMsg(null)
      const r = await moveStage(businessId, entity, recordId, to.key, withNote, where.version)
      if (r.ok) {
        setAsking(null)
        setNote('')
        setMsg({ text: t('Moved to “{stage}”.', { stage: to.label }) })
        router.refresh()
      } else {
        setMsg({ text: r.message, bad: true })
      }
    })

  return (
    <div className="bos-stagetrack">
      <ol className="bos-stagepath" aria-label={t('Steps')}>
        {where.path.map((s, i) => (
          <li key={s.key} className={i === now ? 'is-now' : i < now ? 'is-done' : undefined}
            aria-current={i === now ? 'step' : undefined}>
            {s.label}
          </li>
        ))}
      </ol>
      {nexts.length ? (
        <div className="bos-stagetrack__moves">
          <span className="bos-label">{t('Move to')}</span>
          <div className="bos-inv-buttons">
            {nexts.map((m) => (
              <button key={m.key} type="button" className="btn-ghost" disabled={pending}
                onClick={() => (m.needs_note ? setAsking(m) : go(m, ''))}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {asking ? (
        <form className="bos-stagetrack__note" onSubmit={(e) => { e.preventDefault(); go(asking, note) }}>
          <label>
            <span className="bos-label">{t('Note for “{stage}”', { stage: asking.label })}</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required autoFocus />
          </label>
          <div className="bos-inv-buttons">
            <button type="submit" disabled={pending || !note.trim()}>{t('Move to “{stage}”', { stage: asking.label })}</button>
            <button type="button" className="btn-ghost" onClick={() => { setAsking(null); setNote('') }}>{t('Cancel')}</button>
          </div>
        </form>
      ) : null}
      {msg ? <p role="status" className={msg.bad ? 'bos-inv-warn' : 'bos-hint'}>{msg.text}</p> : null}
      {where.history.length ? (
        <details className="bos-stagetrack__history">
          <summary>{t('Stage history')} ({where.history.length})</summary>
          <ol>
            {where.history.map((h, i) => (
              <li key={i}>
                {h.from ? `${h.from} → ` : ''}<strong>{h.to}</strong>
                {h.note ? <> — “{h.note}”</> : null}
                {h.at ? <span className="bos-hint"> · <LocalTime value={h.at} /></span> : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  )
}
