'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { saveProfile, saveRegister, saveRegistration } from '../../invoices/invoice-actions'
import { codeFor, type Registration, type Setup } from '../../invoices/types'

const SCHEMES = [
  { key: 'regular', label: 'Registered — regular GST', does: 'Tax invoices with CGST + SGST or IGST' },
  { key: 'composition', label: 'Registered — composition scheme', does: 'Bills of supply; no tax is charged' },
  { key: 'unregistered', label: 'Not registered for GST', does: 'Plain bills with no GST details' },
] as const

export function InvoicingSetup({ businessId, setup }: { businessId: string; setup: Setup }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ where: string; text: string; bad?: boolean } | null>(null)
  const p = setup.profile
  const [inclusive, setInclusive] = useState<string>(p ? String(p.prices_include_tax) : '')
  const [roundOff, setRoundOff] = useState<string>(p ? String(p.round_off) : '')
  const [issueOn, setIssueOn] = useState(p?.issue_on ?? '')
  const [advances, setAdvances] = useState(p?.advances_treatment ?? '')
  const [dueDays, setDueDays] = useState(p?.default_due_days === null || p?.default_due_days === undefined ? '' : String(p.default_due_days))
  const [terms, setTerms] = useState(p?.terms ?? '')
  const [bank, setBank] = useState(p?.bank_details ?? '')
  const [caOk, setCaOk] = useState(Boolean(p?.ca_confirmed_at))

  const act = (where: string, fn: () => Promise<{ ok: boolean; message?: string }>, ok: string) =>
    start(async () => {
      setMsg(null)
      const r = await fn()
      setMsg({ where, text: r.ok ? ok : r.message ?? 'That did not save', bad: !r.ok })
      if (r.ok) router.refresh()
    })

  const saveHow = () => {
    if (!inclusive || !roundOff || !issueOn) {
      setMsg({ where: 'how', text: 'Answer the three questions first', bad: true })
      return
    }
    act('how', () => saveProfile(businessId, {
      prices_include_tax: inclusive === 'true', round_off: roundOff === 'true', issue_on: issueOn,
      advances_treatment: advances || null, default_due_days: dueDays === '' ? null : Number(dueDays),
      terms: terms || null, bank_details: bank || null, ca_confirmed: caOk,
    }), 'Saved')
  }

  const active = setup.registrations.filter((r) => r.status === 'active')
  return (
    <div className="bos-works">
      {setup.needs.length ? (
        <section className="bos-card bos-inv-needs" aria-label="Still to do">
          <h2>Still to do</h2>
          <ol>{setup.needs.map((n) => <li key={n}>{n}</li>)}</ol>
        </section>
      ) : (
        <p className="bos-inv-ready" role="status">Billing is set up. Orders and bills are priced and numbered from these settings.</p>
      )}

      <section className="bos-card" aria-labelledby="how-h">
        <h2 id="how-h">1 · How you bill</h2>
        <fieldset className="bos-inv-q">
          <legend>Do your catalogue prices already include GST?</legend>
          <div className="bos-choices">
            <label className="bos-choice"><input type="radio" name="incl" checked={inclusive === 'true'} onChange={() => setInclusive('true')} /> Yes — GST is inside the price</label>
            <label className="bos-choice"><input type="radio" name="incl" checked={inclusive === 'false'} onChange={() => setInclusive('false')} /> No — GST is added on top</label>
          </div>
        </fieldset>
        <fieldset className="bos-inv-q">
          <legend>Round bill totals to the nearest rupee?</legend>
          <div className="bos-choices">
            <label className="bos-choice"><input type="radio" name="round" checked={roundOff === 'true'} onChange={() => setRoundOff('true')} /> Yes — show a round-off line</label>
            <label className="bos-choice"><input type="radio" name="round" checked={roundOff === 'false'} onChange={() => setRoundOff('false')} /> No — bill to the paisa</label>
          </div>
          <p className="bos-fieldhelp">The round-off is always its own line and never changes the tax.</p>
        </fieldset>
        <fieldset className="bos-inv-q">
          <legend>When do website and WhatsApp orders get their bill?</legend>
          <div className="bos-choices bos-choices--stack">
            {Object.entries(setup.issue_on_choices).map(([k, v]) => (
              <label key={k} className="bos-choice"><input type="radio" name="issue" checked={issueOn === k} onChange={() => setIssueOn(k)} /> {v}</label>
            ))}
          </div>
        </fieldset>
        <details className="bos-more" open={Boolean(p)}>
          <summary className="bos-label">More — due dates, terms, bank details, tax treatment</summary>
          <div className="bos-form-grid" style={{ marginTop: '.7rem' }}>
            <label><span className="bos-label">Days to pay (business customers) — optional</span>
              <input inputMode="numeric" value={dueDays} onChange={(e) => setDueDays(e.target.value.replace(/\D/g, ''))} placeholder="e.g. 15" /></label>
            <label>
              <span className="bos-label">Tax on advances received</span>
              <select value={advances} onChange={(e) => setAdvances(e.target.value)}>
                <option value="">Not decided — confirm with your CA</option>
                {Object.entries(setup.advances_choices).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="bos-form-wide"><span className="bos-label">Terms printed on bills — optional</span>
              <textarea rows={2} value={terms} onChange={(e) => setTerms(e.target.value)} maxLength={2000} /></label>
            <label className="bos-form-wide"><span className="bos-label">Bank details for business customers — optional</span>
              <textarea rows={2} value={bank} onChange={(e) => setBank(e.target.value)} maxLength={1000} placeholder="Account name, number, IFSC" /></label>
          </div>
        </details>
        <div className="bos-inv-ca">
          <strong>Confirm with your CA</strong>
          <ul>{setup.confirm_with_ca.map((x) => <li key={x}>{x}</li>)}</ul>
          <label className="bos-toggle">
            <input type="checkbox" checked={caOk} onChange={(e) => setCaOk(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>My CA has checked these settings</span>
          </label>
        </div>
        <div className="bos-inv-buttons">
          <button type="button" onClick={saveHow} disabled={pending}>Save</button>
          {msg?.where === 'how' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
        </div>
      </section>

      <section className="bos-card" aria-labelledby="gst-h">
        <h2 id="gst-h">2 · GST registration</h2>
        <p className="bos-hint">One entry per state you are registered in — or say you are not registered. This decides the document: tax invoice, bill of supply or bill.</p>
        {active.length ? (
          <ul className="bos-inv-regs">
            {active.map((r) => <RegistrationRow key={r.id} r={r} />)}
          </ul>
        ) : null}
        <RegistrationForm key={`reg-${setup.registrations.length}`} setup={setup} pending={pending}
          onSave={(body) => act('gst', () => saveRegistration(businessId, null, body), 'Registration added')} />
        {msg?.where === 'gst' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
      </section>

      <section className="bos-card" aria-labelledby="reg-h">
        <h2 id="reg-h">3 · Billing registers</h2>
        <p className="bos-hint">A register is a billing counter at a location. Each has its own numbers: one unbroken series per GSTIN, financial year (April–March) and register — for example <code>CHN1/26-27/00001</code>.</p>
        {setup.registers.length ? (
          <ul className="bos-inv-regs">
            {setup.registers.map((r) => (
              <li key={r.id}>
                <div>
                  <strong>{r.name}</strong> <span className="bos-tag">{r.code}</span>
                  <p>{r.location_name} · next bill looks like <code>{r.sample_number}</code></p>
                  {r.too_long ? <p className="bos-inv-warn">This number is {r.number_length} characters. GST invoice numbers are limited to 16 — use a shorter code or fewer digits (confirm with your CA).</p> : null}
                </div>
                <span className={`bos-state${r.status === 'active' ? ' is-ready' : ' is-off'}`}>{r.status === 'active' ? 'In use' : 'Off'}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {active.length ? (
          <RegisterForm key={`regs-${setup.registers.length}`} setup={setup} pending={pending}
            onSave={(body) => act('reg', () => saveRegister(businessId, null, body), 'Register added')} />
        ) : <p className="bos-empty">Add your GST registration first.</p>}
        {msg?.where === 'reg' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
      </section>
    </div>
  )
}

function RegistrationRow({ r }: { r: Registration }) {
  return (
    <li>
      <div>
        <strong>{r.trade_name || r.legal_name}</strong>{' '}
        <span className="bos-tag">{SCHEMES.find((s) => s.key === r.scheme)?.label}</span>
        <p>{r.gstin ? `GSTIN ${r.gstin} · ` : ''}{r.state_label}</p>
        {r.composition_declaration ? <p className="bos-fieldhelp">Declaration: {r.composition_declaration}</p> : null}
      </div>
      <span className="bos-state is-ready">{r.document === 'tax_invoice' ? 'Tax invoices' : r.document === 'bill_of_supply' ? 'Bills of supply' : 'Bills'}</span>
    </li>
  )
}

function RegistrationForm({ setup, pending, onSave }: { setup: Setup; pending: boolean; onSave: (b: Record<string, unknown>) => void }) {
  const unreg = setup.registrations.some((r) => r.status === 'active' && r.scheme === 'unregistered')
  const [open, setOpen] = useState(setup.registrations.length === 0)
  const [scheme, setScheme] = useState<'regular' | 'composition' | 'unregistered'>('regular')
  const [gstin, setGstin] = useState('')
  const [legal, setLegal] = useState('')
  const [trade, setTrade] = useState('')
  const [state, setState] = useState('')
  const [address, setAddress] = useState('')
  const [decl, setDecl] = useState('')
  if (unreg) return null
  if (!open) return <button type="button" className="btn-ghost" onClick={() => setOpen(true)}>Add another GST registration</button>
  return (
    <form className="bos-inv-form" onSubmit={(e) => {
      e.preventDefault()
      onSave({ scheme, legal_name: legal, trade_name: trade || undefined, gstin: scheme === 'unregistered' ? undefined : gstin,
        state_code: scheme === 'unregistered' ? state : undefined, address: address || undefined,
        composition_declaration: scheme === 'composition' ? decl : undefined })
    }}>
      <fieldset className="bos-role-options" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
        <legend className="bos-label">Your GST status</legend>
        {SCHEMES.map((s) => (
          <label key={s.key} className={`bos-role-option${scheme === s.key ? ' is-on' : ''}`}>
            <input type="radio" name="scheme" checked={scheme === s.key} onChange={() => setScheme(s.key)} />
            <span><strong>{s.label}</strong><small>{s.does}</small></span>
          </label>
        ))}
      </fieldset>
      <div className="bos-form-grid">
        {scheme !== 'unregistered' ? (
          <label><span className="bos-label">GSTIN</span><input value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase().replace(/\s/g, ''))} maxLength={15} required placeholder="15 characters" /></label>
        ) : (
          <label>
            <span className="bos-label">State</span>
            <select value={state} onChange={(e) => setState(e.target.value)} required>
              <option value="">Choose</option>
              {setup.states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          </label>
        )}
        <label><span className="bos-label">Legal name</span><input value={legal} onChange={(e) => setLegal(e.target.value)} required maxLength={200} /></label>
        <label><span className="bos-label">Trade name — optional</span><input value={trade} onChange={(e) => setTrade(e.target.value)} maxLength={200} /></label>
        <label className="bos-form-wide"><span className="bos-label">Address on bills — optional (else the location&apos;s)</span><input value={address} onChange={(e) => setAddress(e.target.value)} maxLength={500} /></label>
        {scheme === 'composition' ? (
          <label className="bos-form-wide">
            <span className="bos-label">Declaration printed on every bill of supply</span>
            <textarea rows={2} value={decl} onChange={(e) => setDecl(e.target.value)} required maxLength={300}
              placeholder="The wording your CA gives you" />
            <span className="bos-fieldhelp">Confirm the exact wording with your CA. LOCAH prints it as you enter it.</span>
          </label>
        ) : null}
      </div>
      <button type="submit" disabled={pending}>Add registration</button>
    </form>
  )
}

function RegisterForm({ setup, pending, onSave }: { setup: Setup; pending: boolean; onSave: (b: Record<string, unknown>) => void }) {
  const active = setup.registrations.filter((r) => r.status === 'active')
  const uncovered = setup.locations.find((l) => !setup.registers.some((r) => r.location_id === l.id && r.status === 'active'))
  const first = uncovered ?? setup.locations[0]
  const [location, setLocation] = useState(first?.id ?? '')
  const [registration, setRegistration] = useState(active[0]?.id ?? '')
  const [code, setCode] = useState(first ? first.internal_code?.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8) || codeFor(first.name) : 'REG1')
  const [name, setName] = useState('Front counter')
  const [pad, setPad] = useState('5')
  const [open, setOpen] = useState(Boolean(uncovered))
  if (!open) return <button type="button" className="btn-ghost" onClick={() => setOpen(true)}>Add another register</button>
  return (
    <form className="bos-inv-form" onSubmit={(e) => { e.preventDefault(); onSave({ location_id: location, registration_id: registration, code, name, pad: Number(pad) }) }}>
      <div className="bos-form-grid">
        <label><span className="bos-label">Location</span>
          <select value={location} onChange={(e) => setLocation(e.target.value)}>
            {setup.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select></label>
        {active.length > 1 ? (
          <label><span className="bos-label">GST registration</span>
            <select value={registration} onChange={(e) => setRegistration(e.target.value)}>
              {active.map((r) => <option key={r.id} value={r.id}>{r.gstin ?? r.legal_name} · {r.state_label}</option>)}
            </select></label>
        ) : null}
        <label><span className="bos-label">Code</span><input value={code} onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8))} required /></label>
        <label><span className="bos-label">Name</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} /></label>
        <label><span className="bos-label">Digits in the number</span>
          <select value={pad} onChange={(e) => setPad(e.target.value)}>{[3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
      </div>
      <button type="submit" disabled={pending || !code}>Add register</button>
    </form>
  )
}
