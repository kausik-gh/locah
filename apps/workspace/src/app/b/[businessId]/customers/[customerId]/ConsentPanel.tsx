'use client'

import { useState, useTransition } from 'react'
import { LocalTime } from '@/components/LocalTime'
import { changeConsent } from './consent-actions'

export type ConsentRow = {
  id: string
  purpose: string
  purpose_label: string
  channel: string
  source: string
  granted_at: string
  withdrawn_at: string | null
  withdrawn_source: string | null
  open: boolean
}

/* What a customer can agree to (Capability Universe §12.4, §25.1). Order and
   booking messages follow the customer's own action and need no opt-in, so
   they are not listed here. */
const ASKS = [
  { purpose: 'marketing', channel: 'whatsapp', title: 'Offers on WhatsApp', help: 'Promotions and new arrivals.' },
  { purpose: 'reminders', channel: 'whatsapp', title: 'Reminders on WhatsApp', help: 'Renewals, appointments and dues.' },
  { purpose: 'photos_public', channel: 'any', title: 'Photos may be shown', help: 'On your website or social pages.' },
]

const SOURCES: Record<string, string> = {
  staff_recorded: 'recorded by your team',
  checkout_checkbox: 'ticked at checkout',
  whatsapp_opt_in: 'opted in on WhatsApp',
  my_activity: 'from their own account',
}

const HOW = ['Told us in person', 'On a phone call', 'In writing']

export function ConsentPanel({
  businessId,
  customerId,
  history,
  canChange,
}: {
  businessId: string
  customerId: string
  history: ConsentRow[]
  canChange: boolean
}) {
  const [pending, start] = useTransition()
  const [asking, setAsking] = useState<string | null>(null)
  const [how, setHow] = useState(HOW[0])
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)

  const current = (purpose: string, channel: string) =>
    history.find((h) => h.purpose === purpose && h.channel === channel && h.open) ?? null
  const last = (purpose: string, channel: string) =>
    history.find((h) => h.purpose === purpose && h.channel === channel) ?? null

  const act = (purpose: string, channel: string, granted: boolean) => {
    setMsg(null)
    start(async () => {
      const r = await changeConsent(businessId, customerId, {
        purpose,
        channel,
        granted,
        note: granted ? how : undefined,
      })
      if (r.ok) {
        setAsking(null)
        setMsg({ text: granted ? 'Agreement recorded.' : 'Withdrawn. Nothing more will be sent for this.' })
      } else setMsg({ text: r.message, bad: true })
    })
  }

  return (
    <section className="bos-section" aria-labelledby="consent-h">
      <h2 className="bos-section__title" id="consent-h">What they agreed to</h2>
      <ul className="bos-consents">
        {ASKS.map((a) => {
          const on = current(a.purpose, a.channel)
          const prev = last(a.purpose, a.channel)
          const key = `${a.purpose}:${a.channel}`
          return (
            <li key={key}>
              <div>
                <strong>{a.title}</strong>
                <p>
                  {on ? (
                    <>
                      Agreed <LocalTime value={on.granted_at} mode="date" /> · {SOURCES[on.source] ?? on.source}
                    </>
                  ) : prev?.withdrawn_at ? (
                    <>
                      Withdrawn <LocalTime value={prev.withdrawn_at} mode="date" />
                    </>
                  ) : (
                    <>Not asked yet · {a.help}</>
                  )}
                </p>
              </div>
              <div className="bos-consents__act">
                <span className={`bos-state${on ? ' is-ready' : ' is-off'}`}>{on ? 'Yes' : 'No'}</span>
                {canChange && asking !== key ? (
                  on ? (
                    <button type="button" className="btn-quiet" disabled={pending} onClick={() => act(a.purpose, a.channel, false)}>
                      Withdraw
                    </button>
                  ) : (
                    <button type="button" className="btn-quiet" disabled={pending} onClick={() => setAsking(key)}>
                      Record yes
                    </button>
                  )
                ) : null}
              </div>
              {asking === key ? (
                <div className="bos-consents__ask">
                  <label>
                    <span className="bos-label">How did they agree?</span>
                    <select value={how} onChange={(e) => setHow(e.target.value)}>
                      {HOW.map((h) => (
                        <option key={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                  <button type="button" disabled={pending} onClick={() => act(a.purpose, a.channel, true)}>
                    {pending ? 'Saving…' : 'Record agreement'}
                  </button>
                  <button type="button" className="btn-quiet" onClick={() => setAsking(null)} disabled={pending}>
                    Cancel
                  </button>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">
        {msg?.text ?? ''}
      </p>
      {history.length > 0 ? (
        <details className="bos-more">
          <summary className="bos-hint">Full history ({history.length})</summary>
          <ul className="bos-consent-log">
            {history.map((h) => (
              <li key={h.id}>
                {h.purpose_label} ({h.channel}) — agreed <LocalTime value={h.granted_at} />
                {h.withdrawn_at ? (
                  <>
                    , withdrawn <LocalTime value={h.withdrawn_at} />
                  </>
                ) : null}{' '}
                · {SOURCES[h.source] ?? h.source}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
