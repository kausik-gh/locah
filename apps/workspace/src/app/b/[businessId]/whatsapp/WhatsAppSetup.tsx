'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import {
  completeSignup, connectSandbox, disconnect, sandboxInbound, saveMyAlerts, saveSettings, submitTemplates,
} from './whatsapp-actions'
import type { Setup } from './types'

type FB = {
  init: (o: Record<string, unknown>) => void
  login: (cb: (r: { authResponse?: { code?: string } }) => void, o: Record<string, unknown>) => void
}
declare global {
  interface Window { FB?: FB; fbAsyncInit?: () => void }
}

const STATUS_WORDS: Record<string, string> = { approved: 'Approved', submitted: 'Waiting for WhatsApp', rejected: 'Rejected', paused: 'Paused' }

/** Meta's Embedded Signup in the owner's browser (activation required: needs LOCAH's Meta app). */
function loadFacebook(appId: string, version: string): Promise<FB> {
  return new Promise((resolve, reject) => {
    if (window.FB) return resolve(window.FB)
    window.fbAsyncInit = () => {
      window.FB!.init({ appId, autoLogAppEvents: true, xfbml: false, version })
      resolve(window.FB!)
    }
    const s = document.createElement('script')
    s.src = 'https://connect.facebook.net/en_US/sdk.js'
    s.async = true
    s.onerror = () => reject(new Error('Could not reach Facebook to start the connection'))
    document.body.appendChild(s)
  })
}

export function WhatsAppSetup({ businessId, setup, canConfigure }: { businessId: string; setup: Setup; canConfigure: boolean }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ where: string; text: string; bad?: boolean } | null>(null)
  const ch = setup.channel
  const [phone, setPhone] = useState('')
  const [coexist, setCoexist] = useState(true)
  const [lang, setLang] = useState(setup.settings.language)
  const [updates, setUpdates] = useState(setup.settings.customer_updates)
  const [pause, setPause] = useState(String(setup.settings.human_pause_hours))
  const [cod, setCod] = useState(setup.settings.cod_allowed)
  const [cap, setCap] = useState(setup.settings.first_order_cod_cap === null ? '' : String(setup.settings.first_order_cod_cap))
  const [copied, setCopied] = useState(false)
  const mine = setup.alerts.mine
  const [alertPhone, setAlertPhone] = useState(mine?.phone ? `+${mine.phone}` : '')
  const [alertKinds, setAlertKinds] = useState<string[]>(mine?.kinds ?? Object.keys(setup.alerts.kinds).slice(0, 2))
  const [alertsOn, setAlertsOn] = useState(Boolean(mine?.enabled))
  const [test, setTest] = useState({ from: '+91 98765 00001', name: 'Test customer', text: 'Hi, are you open today?' })
  const run = (where: string, fn: () => Promise<{ ok: boolean; message?: string }>, ok: string) =>
    start(async () => {
      setMsg(null)
      const r = await fn()
      setMsg({ where, text: r.ok ? ok : r.message ?? 'That did not work', bad: !r.ok })
      if (r.ok) router.refresh()
    })
  const status = (where: string) => (msg?.where === where ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null)

  const connectMeta = () =>
    start(async () => {
      setMsg(null)
      if (!setup.meta) return
      try {
        const fb = await loadFacebook(setup.meta.app_id, setup.meta.graph_version)
        let session: { phone_number_id?: string; waba_id?: string } = {}
        const listen = (e: MessageEvent) => {
          if (!/\.facebook\.com$/.test(new URL(e.origin).hostname)) return
          try {
            const data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data
            if (data?.type === 'WA_EMBEDDED_SIGNUP' && data.data) session = data.data
          } catch { /* not ours */ }
        }
        window.addEventListener('message', listen)
        const code = await new Promise<string | null>((resolve) => fb.login((r) => resolve(r.authResponse?.code ?? null), {
          config_id: setup.meta!.config_id, response_type: 'code', override_default_response_type: true,
          extras: { setup: {}, sessionInfoVersion: '3', ...(coexist ? { featureType: 'whatsapp_business_app_onboarding' } : {}) },
        }))
        window.removeEventListener('message', listen)
        if (!code || !session.phone_number_id || !session.waba_id) return setMsg({ where: 'connect', text: 'The connection was not finished', bad: true })
        const r = await completeSignup(businessId, { code, phone_number_id: session.phone_number_id, waba_id: session.waba_id, coexistence: coexist })
        setMsg({ where: 'connect', text: r.ok ? 'Connected' : r.message, bad: !r.ok })
        if (r.ok) router.refresh()
      } catch (e) {
        setMsg({ where: 'connect', text: (e as Error).message, bad: true })
      }
    })

  const approvedCount = setup.templates.filter((t) => t.phase === 'P1' && t.status[lang] === 'approved').length
  const p1 = setup.templates.filter((t) => t.phase === 'P1')

  return (
    <div className="bos-works">
      <section className="bos-card" aria-labelledby="num-h">
        <h2 id="num-h">Your WhatsApp number</h2>
        {ch ? (
          <>
            <div className="bos-wa-number">
              <strong>{ch.display_phone}</strong>
              <span>{ch.display_name}</span>
              <span className="bos-tag">{ch.status === 'connected' ? 'Connected' : ch.status}</span>
              {ch.sandbox ? <span className="bos-tag bos-tag--warn">Test number</span> : null}
              {ch.coexistence ? <span className="bos-tag">Also on the WhatsApp Business app</span> : null}
            </div>
            {ch.sandbox ? <p className="bos-hint">A test number on this LOCAH stack: messages are recorded in the inbox but not delivered to anyone’s phone.</p> : null}
            {ch.quality_rating ? <p className="bos-hint">WhatsApp quality rating: {ch.quality_rating}{ch.messaging_limit ? ` · daily limit ${ch.messaging_limit}` : ''}</p> : null}
            {ch.last_error ? <p className="bos-status bos-error">Last problem: {ch.last_error}</p> : null}
            {canConfigure ? (
              <div className="bos-inv-buttons">
                <button type="button" className="btn-quiet" disabled={pending}
                  onClick={() => { if (confirm('Disconnect this number? Automatic messages stop until you connect again.')) run('connect', () => disconnect(businessId), 'Disconnected') }}>
                  Disconnect
                </button>
              </div>
            ) : null}
          </>
        ) : canConfigure ? (
          <>
            <p className="bos-hint">Connect the number your customers already message. LOCAH sends order and booking updates and reminders from it, and every chat lands in one inbox.</p>
            {setup.meta_ready ? (
              <>
                <label className="bos-toggle">
                  <input type="checkbox" checked={coexist} onChange={(e) => setCoexist(e.target.checked)} />
                  <span className="bos-toggle__track" aria-hidden />
                  <span>I use the WhatsApp Business app on this number and want to keep using it</span>
                </label>
                <div className="bos-inv-buttons"><button type="button" disabled={pending} onClick={connectMeta}>Connect with WhatsApp</button></div>
              </>
            ) : (
              <p className="bos-wa-activation" role="status">
                Connecting a real number needs LOCAH’s WhatsApp Business partnership with Meta, which is being switched on.
                Until then no messages are sent from your number.
              </p>
            )}
            {setup.sandbox_available ? (
              <form className="bos-inv-form" onSubmit={(e) => { e.preventDefault(); run('connect', () => connectSandbox(businessId, { display_phone: phone }), 'Test number connected') }}>
                <p className="bos-hint" style={{ margin: 0 }}>On this test stack you can connect a test number to try everything end to end.</p>
                <label><span className="bos-label">Test number</span><input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+91 98400 00000" /></label>
                <button type="submit" disabled={pending || phone.replace(/\D/g, '').length < 10}>Connect test number</button>
              </form>
            ) : null}
          </>
        ) : <p className="bos-hint">The owner connects the business’s WhatsApp number.</p>}
        {status('connect')}
      </section>

      {ch ? (
        <section className="bos-card" aria-labelledby="upd-h">
          <h2 id="upd-h">What customers get automatically</h2>
          <ul className="bos-wa-updates">
            {Object.entries(setup.customer_updates).map(([k, label]) => (
              <li key={k}>
                <label className="bos-toggle">
                  <input type="checkbox" disabled={!canConfigure} checked={updates[k] !== false} onChange={(e) => setUpdates({ ...updates, [k]: e.target.checked })} />
                  <span className="bos-toggle__track" aria-hidden />
                  <span>{label}</span>
                </label>
              </li>
            ))}
          </ul>
          <p className="bos-hint">Timed messages — {Object.values(setup.ladder_updates).join(', ').toLowerCase()} — are switched in <Link href={`/b/${businessId}/settings/automations`}>Automations</Link>.</p>
          <div className="bos-form-grid">
            <label><span className="bos-label">Language for customers</span>
              <select value={lang} disabled={!canConfigure} onChange={(e) => setLang(e.target.value as typeof lang)}>
                {Object.entries(setup.languages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></label>
            <label><span className="bos-label">After a person replies, LOCAH’s automatic replies wait (hours)</span>
              <input inputMode="numeric" disabled={!canConfigure} value={pause} onChange={(e) => setPause(e.target.value.replace(/\D/g, ''))} /></label>
          </div>
          {canConfigure ? (
            <div className="bos-inv-buttons">
              <button type="button" disabled={pending} onClick={() => run('updates', () => saveSettings(businessId, { language: lang, customer_updates: updates, human_pause_hours: Number(pause || 12) }), 'Saved')}>Save</button>
              {status('updates')}
            </div>
          ) : null}
        </section>
      ) : null}

      {ch ? (
        <section className="bos-card" aria-labelledby="entry-h">
          <h2 id="entry-h">Customers order and book here</h2>
          {setup.entry ? (
            <>
              <p className="bos-hint">
                When a customer sends “menu”, LOCAH answers with buttons — no typing, no AI — and every order, booking or
                question lands in the same place as your website’s. Prices and stock come only from your catalogue.
              </p>
              <ul className="bos-wa-journeys">
                {setup.entry.journeys.includes('order') ? <li><strong>Order</strong> — pick items, delivery or pickup, pay on delivery</li> : null}
                {setup.entry.journeys.includes('book') ? <li><strong>Book</strong> — a service, a day and a free time from your opening hours</li> : null}
                {setup.entry.journeys.includes('enquire') ? <li><strong>Ask a question</strong> — saved as an enquiry for your team</li> : null}
                {setup.entry.journeys.some((j) => j === 'order' || j === 'book') ? <li><strong>Track, repeat, change or cancel</strong> — their own orders and bookings, within your policy</li> : null}
                {setup.entry.journeys.includes('dues') ? <li><strong>What do I owe</strong> — their khata balance and unpaid bills, with a link to pay</li> : null}
                <li><strong>Talk to a person</strong> — always there; the chat comes to your inbox</li>
              </ul>
              <div className="bos-wa-entry">
                <figure className="bos-wa-qr">
                  {/* Generated on the server from the business's own link. */}
                  <div aria-label={`QR code: ${setup.entry.label}`} role="img" dangerouslySetInnerHTML={{ __html: setup.entry.qr_svg }} />
                  <figcaption>Scan to {setup.entry.label.replace(' on WhatsApp', '').toLowerCase()} on WhatsApp</figcaption>
                </figure>
                <div>
                  <p className="bos-label">Your link</p>
                  <p className="bos-wa-link"><a href={setup.entry.href} target="_blank" rel="noreferrer">{setup.entry.href}</a></p>
                  <div className="bos-inv-buttons">
                    <button type="button" className="btn-ghost" onClick={() => { void navigator.clipboard?.writeText(setup.entry!.href); setCopied(true) }}>{copied ? 'Copied' : 'Copy link'}</button>
                    <a className="btn btn-ghost" download="whatsapp-qr.svg" href={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.entry.qr_svg)}`}>Download QR</a>
                  </div>
                  <p className="bos-hint" style={{ marginTop: '.6rem' }}>
                    Print the QR for your counter and packaging. Your website shows “{setup.entry.label}”, and so does your Marketplace listing.
                    {setup.entry.test_number ? ' This is a test number, so the link will not open a real chat.' : ''}
                  </p>
                </div>
              </div>
              <fieldset className="bos-inv-q" disabled={!canConfigure}>
                <legend>Paying for WhatsApp orders</legend>
                <label className="bos-toggle">
                  <input type="checkbox" checked={cod} onChange={(e) => setCod(e.target.checked)} />
                  <span className="bos-toggle__track" aria-hidden />
                  <span>Customers can pay on delivery or at pickup</span>
                </label>
                {cod ? (
                  <label style={{ display: 'grid', maxWidth: '22rem', marginTop: '.5rem' }}>
                    <span className="bos-label">First order: pay on delivery up to (₹, leave empty for no limit)</span>
                    <input inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value.replace(/[^\d.]/g, ''))} placeholder="No limit" />
                  </label>
                ) : (
                  <p className="bos-hint">Online payment links need a payment provider, which is being switched on — until then a person finishes these orders.</p>
                )}
                {canConfigure ? (
                  <div className="bos-inv-buttons">
                    <button type="button" disabled={pending} onClick={() => run('pay', () => saveSettings(businessId, { cod_allowed: cod, first_order_cod_cap: cap ? Number(cap) : null }), 'Saved')}>Save payment rules</button>
                    {status('pay')}
                  </div>
                ) : null}
              </fieldset>
            </>
          ) : (
            <p className="bos-hint">
              Switch on <Link href={`/b/${businessId}/modules`}>Orders, Bookings or Enquiries</Link> and customers can order, book or ask
              right here with buttons — the same records your website creates.
            </p>
          )}
        </section>
      ) : null}

      {ch ? (
        <section className="bos-card" aria-labelledby="tpl-h">
          <h2 id="tpl-h">Message templates <span className="bos-tag">{approvedCount} of {p1.length} approved in {setup.languages[lang]}</span></h2>
          <p className="bos-hint">WhatsApp approves each message LOCAH may send outside a customer’s 24-hour reply window.</p>
          <ul className="bos-wa-templates">
            {p1.map((t) => (
              <li key={t.key}>
                <div>
                  <strong>{t.label}</strong>
                  <small>{t.sent_when}{t.audience === 'staff' ? ' · to your team' : ''}</small>
                  <p className="bos-wa-preview">{t.bodies[lang] ?? t.bodies.en}</p>
                </div>
                <span className="bos-wa-langs">
                  {Object.entries(setup.languages).map(([code, name]) => (
                    <span key={code} className={`bos-tag${t.status[code] === 'approved' ? ' bos-tag--good' : t.status[code] === 'rejected' ? ' bos-tag--bad' : ''}`}>
                      {name}: {t.status[code] ? STATUS_WORDS[t.status[code] as string] : 'Not sent'}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          {canConfigure && p1.some((t) => Object.values(t.status).some((s) => !s || s === 'rejected')) ? (
            <div className="bos-inv-buttons">
              <button type="button" disabled={pending} onClick={() => run('tpl', () => submitTemplates(businessId), 'Sent to WhatsApp for approval')}>Send for approval</button>
              {status('tpl')}
            </div>
          ) : null}
        </section>
      ) : null}

      {ch && Object.keys(setup.alerts.kinds).length ? (
        <section className="bos-card" aria-labelledby="al-h">
          <h2 id="al-h">Your own WhatsApp alerts</h2>
          <p className="bos-hint">Sent from the business number to your phone. Only what your role lets you see.</p>
          <label className="bos-toggle">
            <input type="checkbox" checked={alertsOn} onChange={(e) => setAlertsOn(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>Send me alerts on WhatsApp</span>
          </label>
          {alertsOn ? (
            <div className="bos-inv-form" style={{ borderTop: 0, paddingTop: 0 }}>
              <label><span className="bos-label">My WhatsApp number</span><input value={alertPhone} onChange={(e) => setAlertPhone(e.target.value)} inputMode="tel" placeholder="+91 98400 00000" /></label>
              <fieldset className="bos-inv-q">
                <legend>Tell me about</legend>
                <div className="bos-choices bos-choices--stack">
                  {Object.entries(setup.alerts.kinds).map(([k, label]) => (
                    <label key={k} className="bos-choice">
                      <input type="checkbox" checked={alertKinds.includes(k)} onChange={(e) => setAlertKinds(e.target.checked ? [...alertKinds, k] : alertKinds.filter((x) => x !== k))} />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          ) : null}
          <div className="bos-inv-buttons">
            <button type="button" disabled={pending} onClick={() => run('alerts', () => saveMyAlerts(businessId, { enabled: alertsOn, phone: alertPhone, kinds: alertKinds }), alertsOn ? 'Alerts on' : 'Alerts off')}>Save my alerts</button>
            {status('alerts')}
          </div>
        </section>
      ) : null}

      {setup.meter ? (
        <section className="bos-card" aria-labelledby="use-h">
          <h2 id="use-h">Messages this month</h2>
          <p className="bos-wa-meter"><strong>{setup.meter.used.toLocaleString('en-IN')}</strong> sent{setup.meter.cap !== null ? ` of your ${setup.meter.cap.toLocaleString('en-IN')} limit` : ' · no limit set'}</p>
          <p className="bos-hint">WhatsApp charges per message by kind; set a monthly limit in <Link href={`/b/${businessId}/settings/usage`}>Usage & limits</Link>. At the limit, LOCAH stops sending and tells you.</p>
        </section>
      ) : null}

      {ch?.sandbox && canConfigure ? (
        <section className="bos-card" aria-labelledby="try-h">
          <h2 id="try-h">Try it: a customer writes to your test number</h2>
          <form className="bos-form-grid" onSubmit={(e) => { e.preventDefault(); run('try', () => sandboxInbound(businessId, { from_phone: test.from, name: test.name, text: test.text }), 'Delivered to the inbox') }}>
            <label><span className="bos-label">From</span><input value={test.from} onChange={(e) => setTest({ ...test, from: e.target.value })} /></label>
            <label><span className="bos-label">Name</span><input value={test.name} onChange={(e) => setTest({ ...test, name: e.target.value })} /></label>
            <label className="bos-form-wide"><span className="bos-label">Message</span><input value={test.text} onChange={(e) => setTest({ ...test, text: e.target.value })} /></label>
            <div className="bos-inv-buttons bos-form-wide"><button type="submit" disabled={pending}>Send as the customer</button>{status('try')}</div>
          </form>
        </section>
      ) : null}
    </div>
  )
}
