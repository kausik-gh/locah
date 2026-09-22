'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { BusinessInterviewData, InterviewCommand, InterviewFactKey } from '@platform/contracts'
import { finishInterviewUpload, interviewAction, reloadInterview, startInterviewUpload } from './actions'
import { ROLE_LABELS, ROLE_ORDER, roleFromText, type MediaRole } from './attachment'
import { VoicePanel } from './voice/VoicePanel'

const LABELS: Record<InterviewFactKey, string> = {
  description: 'Your business', classification: 'Kind of business', operating_model: 'How you work',
  locations: 'Where to find you', offerings: 'What you sell or do', customer_actions: 'What visitors should do',
  operational_characteristics: 'How it works', brand: 'Your brand', tone: 'Your voice', colours: 'Your colours',
  opening_hours: 'Opening hours', phone: 'Phone', email: 'Email', website_priorities: 'What matters most',
}
type Change = Omit<InterviewCommand, 'revision' | 'request_id'>
/** An image that is uploaded and waiting only for the owner to say what it is. */
type Staged = { assetId: string; filename: string }

export function BusinessInterview({ initial }: { initial: BusinessInterviewData }) {
  const [data, setData] = useState(initial)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [field, setField] = useState<InterviewFactKey | ''>('')
  const [lastAnswer, setLastAnswer] = useState('')
  // The owner's own words, shown the instant they send them. Replaced by server
  // state on the next response — never a fabricated assistant reply.
  const [sending, setSending] = useState('')
  const [staged, setStaged] = useState<Staged | null>(null)
  const [mode, setMode] = useState<'chat' | 'voice'>('chat')
  const [uploading, setUploading] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const stream = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const bp = data.blueprint
  const facts = { ...bp.known_facts, ...bp.unconfirmed_facts }
  const pendingChoices = bp.recommended_modules.some(m => m.choice === 'pending')
  const answered = Object.keys(facts).length

  useEffect(() => {
    stream.current?.scrollTo({ top: stream.current.scrollHeight, behavior: 'smooth' })
  }, [bp.messages.length, sending])

  async function send(change: Change) {
    setBusy(true); setError('')
    if (change.action === 'turn' && change.text) setSending(change.text)
    try {
      const res = await interviewAction(bp.business_id, { ...change, revision: bp.revision, request_id: crypto.randomUUID() })
      if (!res.ok) {
        setError(res.error)
        if (res.stale) { const latest = await reloadInterview(bp.business_id); if (latest.ok) setData(latest.data) }
        return false
      }
      setData(res.data)
      if (change.action === 'turn') { setLastAnswer(change.text || ''); setText(''); setField('') }
      if (change.action === 'build') router.push(`/start/${bp.business_id}/website`)
      return true
    } catch { setError('Could not save that change. Your previous answers are safe. Please retry.'); return false }
    finally { setBusy(false); setSending('') }
  }

  /**
   * A spoken turn, handled by exactly the same command a typed one uses.
   *
   * Locah's reply is whatever the interview decided — the realtime model is
   * told what to say, it does not choose. That is what keeps one Blueprint
   * authoritative across both ways of talking to it.
   */
  async function speakTurn(transcript: string): Promise<{ say: string; sufficient: boolean }> {
    const res = await interviewAction(bp.business_id, {
      action: 'turn', text: transcript, revision: bp.revision, request_id: crypto.randomUUID(),
    })
    if (!res.ok) {
      if (res.stale) { const latest = await reloadInterview(bp.business_id); if (latest.ok) setData(latest.data) }
      return { say: 'I could not save that just now — could you say it once more?', sufficient: false }
    }
    setData(res.data)
    const next = res.data.blueprint
    const reply = next.messages.filter(m => m.role === 'assistant').slice(-1)[0]?.text
    return {
      say: reply || 'Tell me a little more about your business.',
      sufficient: next.completion_state.sufficient,
    }
  }

  /** Upload now so the transfer overlaps with typing; ask what it is only if the words do not say. */
  async function attach(file: File) {
    setUploading(true); setError('')
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose an image smaller than 10 MB.')
      const guess = roleFromText(text)
      const start = await startInterviewUpload(bp.business_id, guess ?? 'business', file.type, file.size, file.name)
      if (!start.ok) throw new Error(start.error)
      const uploaded = await fetch(start.uploadUrl, { method: 'PUT', headers: { 'Content-Type': file.type }, body: file })
      if (!uploaded.ok) throw new Error('The image did not upload. Please try again.')
      const complete = await finishInterviewUpload(bp.business_id, start.assetId)
      if (!complete.ok) throw new Error(complete.error)
      if (guess) await saveAttachment(start.assetId, file.name, guess)
      else setStaged({ assetId: start.assetId, filename: file.name })
    } catch (e) { setError(e instanceof Error ? e.message : 'Image upload failed.') }
    finally { setUploading(false) }
  }

  async function saveAttachment(assetId: string, filename: string, role: MediaRole) {
    const ok = await send({ action: 'media', media: { asset_id: assetId, role, label: filename, source: 'USER_UPLOAD' } })
    if (ok) setStaged(null)
  }

  const waiting = busy && Boolean(sending)

  return <div className="bi">
    <header className="bi-heading">
      <div><p className="bi-eyebrow">A LITTLE CONVERSATION. YOUR NEXT CHAPTER.</p>
        <h1>{bp.identity.display_name?.value}</h1>
        <p>Tell us what makes your business yours. You can leave and come back any time.</p></div>
      <span className="bi-saved" role="status">{busy ? 'Saving…' : 'Progress saved'}</span>
    </header>
    <div className="bi-layout">
      <section className="bi-conversation" aria-label="Business interview">
        <div className="bi-modes" role="tablist" aria-label="How to answer">
          <button role="tab" type="button" aria-selected={mode === 'chat'} onClick={() => setMode('chat')}>Chat with Locah</button>
          <button role="tab" type="button" aria-selected={mode === 'voice'} disabled={!data.voice.available}
            title={data.voice.reason} onClick={() => setMode('voice')}>
            {data.voice.available ? 'Talk to Locah' : 'Talk to Locah · not available yet'}
          </button>
        </div>
        {mode === 'voice' ? <VoicePanel businessId={bp.business_id} data={data}
          onTurn={speakTurn} onSwitchToChat={() => setMode('chat')} /> : null}
        {mode === 'chat' ? <><div className="bi-messages" role="log" aria-live="polite" aria-relevant="additions" ref={stream}>
          {bp.messages.map((message, i) => <div className={`bi-message bi-message--${message.role}`} key={`${message.at}-${i}`}>
            <span>{message.role === 'assistant' ? 'LOCAH' : 'YOU'}</span><p>{message.text}</p>
          </div>)}
          {waiting && <>
            <div className="bi-message bi-message--user bi-message--pending"><span>YOU</span><p>{sending}</p></div>
            <div className="bi-message bi-message--assistant bi-thinking" aria-label="Locah is reading your answer">
              <span>LOCAH</span><p><i /><i /><i /></p>
            </div>
          </>}
        </div>
        {error && <p className="ob-error" role="alert">{error}</p>}

        {staged && <div className="bi-staged" role="group" aria-label="What is this image?">
          <p><strong>{staged.filename}</strong> is ready. What is it?</p>
          <div className="bi-choices">{ROLE_ORDER.map(role => <button key={role} className="lc-btn" type="button" disabled={busy}
            onClick={() => void saveAttachment(staged.assetId, staged.filename, role)}>{ROLE_LABELS[role]}</button>)}</div>
        </div>}

        <form className="bi-compose" onSubmit={e => { e.preventDefault(); void send({ action: 'turn', text, ...(field ? { field } : {}) }) }}>
          <label htmlFor="interview-message">{field ? `Update: ${LABELS[field]}` : 'Your reply'}</label>
          <textarea ref={input} id="interview-message" value={text} onChange={e => setText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && text.trim()) { e.preventDefault(); void send({ action: 'turn', text, ...(field ? { field } : {}) }) } }}
            maxLength={4000} required rows={3} disabled={busy} placeholder="In your own words… you can attach a photo or logo too." />
          <div className="bi-compose-actions">
            <button className="lc-btn lc-btn--primary" disabled={busy || !text.trim()}>{busy ? 'Saving…' : 'Send reply →'}</button>
            <label className="bi-clip">
              {uploading ? 'Uploading…' : '📎 Attach image'}
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy || uploading}
                onChange={e => { const file = e.target.files?.[0]; if (file) void attach(file); e.target.value = '' }} />
            </label>
            {field && <button className="lc-btn" type="button" onClick={() => setField('')}>Cancel correction</button>}
          </div>
          <p className="ob-help bi-hint">Say what a picture is as you attach it — “this is our logo”, “photos of our shop” — and it goes to the right place.</p>
        </form>

        </> : null}

        {lastAnswer && bp.last_turn?.fallback_reason && bp.remaining_questions[0] && <div className="bi-fallback">
          <p>AI couldn’t organise your answer. You can save it directly as “{LABELS[bp.remaining_questions[0].field]}”, then review it.</p>
          <button className="lc-btn" disabled={busy} onClick={() => void send({ action: 'turn', field: bp.remaining_questions[0].field, text: lastAnswer })}>Save as answer</button>
        </div>}

        {bp.media_assets.length > 0 && <ul className="bi-attached">
          {bp.media_assets.map(asset => <li key={asset.asset_id}>✓ {asset.label || 'Image'} — {ROLE_LABELS[asset.role]}</li>)}
        </ul>}
        {data.image_generation.available && <details className="bi-artwork"><summary>No cover photo? Locah can draw one · optional</summary>
          <p className="ob-help">{data.image_generation.reason}</p>
          <button className="lc-btn" disabled={busy || bp.media_generation_requests.length > 0 || bp.completion_state.status === 'built'}
            onClick={() => void send({ action: 'image' })}>{bp.media_generation_requests.length ? 'Cover artwork requested' : 'Draw cover artwork after building'}</button>
        </details>}
      </section>

      <aside className="bi-summary" aria-label="What Locah understood">
        <p className="bi-eyebrow">WHAT WE’VE UNDERSTOOD</p>
        <h2>{bp.completion_state.sufficient ? 'Ready for your review' : 'Taking shape'}</h2>
        <p className="bi-progress" role="status">{bp.completion_state.sufficient
          ? 'Enough for a first website. Everything else can wait.'
          : `${answered} ${answered === 1 ? 'detail' : 'details'} so far · ${bp.remaining_questions.length} to go`}</p>
        <dl>{Object.entries(facts).map(([key, fact]) => fact && <div key={key}>
          <dt>{LABELS[key as InterviewFactKey]} <span>{fact.confirmation === 'confirmed' ? 'Confirmed' : 'Please review'}</span></dt>
          <dd>{fact.value}</dd>
          {bp.unconfirmed_facts[key as InterviewFactKey] && bp.known_facts[key as InterviewFactKey] && <small>Previously: {bp.known_facts[key as InterviewFactKey]?.value}</small>}
          <button className="bi-text-button" disabled={busy} onClick={() => { setField(key as InterviewFactKey); setText(fact.value); input.current?.focus() }}>Change</button>
        </div>)}</dl>
        {!Object.keys(facts).length && <p>Your details will appear here as we talk.</p>}
        <details><summary>Add or correct a detail</summary>
          <select aria-label="Detail to update" value={field} onChange={e => { setField(e.target.value as InterviewFactKey); input.current?.focus() }}>
            <option value="">Choose a detail</option>{Object.entries(LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </details>
        {bp.completion_state.sufficient && <>
          <p className="ob-help">Suggested starting point: {data.classification_seed.replaceAll('_', ' ')}. This does not add paid tools.</p>
          <button className="lc-btn" disabled={busy || bp.completion_state.confirmed} onClick={() => void send({ action: 'confirm' })}>
            {bp.completion_state.confirmed ? '✓ Details confirmed' : 'These details are correct'}
          </button>
        </>}
      </aside>
    </div>
    {bp.completion_state.sufficient && <section className="bi-finish" aria-label="Review and build">
      <h2>A few choices. Then it’s yours.</h2>
      {bp.unsupported_requests.map(gap => <p className="bi-gap" key={gap.normalized_intent}><strong>You asked: {gap.original_request}</strong><br />{gap.why_unsupported}</p>)}
      {bp.recommended_modules.length > 0 && <>
        <h3>Useful tools for what you want to do</h3><p>Only the tools you approve will be considered. Some still need a plan or setup.</p>
        <div className="bi-tool-grid">{bp.recommended_modules.map(module => <article className="bi-tool" key={module.module_id}>
          <h4>{module.label}</h4><p>{module.reason}</p><p className="ob-help">{module.availability_reason}</p>
          <div className="bi-choices">
            <button className="lc-btn" disabled={busy} aria-pressed={module.choice === 'approved'} onClick={() => void send({ action: 'choices', choices: { [module.module_id]: 'approved' } })}>Use this</button>
            <button className="lc-btn" disabled={busy} aria-pressed={module.choice === 'declined'} onClick={() => void send({ action: 'choices', choices: { [module.module_id]: 'declined' } })}>Not now</button>
          </div>
        </article>)}</div>
        <button className="bi-text-button" disabled={busy} onClick={() => void send({ action: 'choices', choices: Object.fromEntries(bp.recommended_modules.map(m => [m.module_id, 'declined'])) })}>Continue without these tools</button>
      </>}
      <details><summary>Choose your starting design · optional</summary>
        <div className="bi-template-grid">{data.templates.filter(t => t.available).map(template => <button key={template.id}
          className="bi-template" disabled={busy} aria-pressed={bp.template_preferences.template_id === template.id}
          onClick={() => void send({ action: 'template', template_id: template.id })}>
          <span className="bi-swatches" aria-hidden="true"><i style={{ background: template.primary_color }} /><i style={{ background: template.accent_color }} /></span>
          <strong>{template.name}</strong><span>{template.look.join(' · ')}</span><small>{template.description}</small>
        </button>)}</div>
      </details>
      <div className="bi-build"><p>Your first preview appears immediately. Personalization runs in the background.<br />Nothing is published until you choose to publish.</p>
        {bp.completion_state.status === 'built' ? <Link className="lc-btn lc-btn--primary" href={`/start/${bp.business_id}/website`}>Open your website</Link> :
          <button className="lc-btn lc-btn--primary lc-btn--lg" disabled={busy || !bp.completion_state.confirmed || pendingChoices}
            onClick={() => void send({ action: 'build' })}>Build my website →</button>}
        {!bp.completion_state.confirmed && <small>Confirm your details above first.</small>}
        {pendingChoices && <small>Choose your tools, or continue without them.</small>}
      </div>
    </section>}
  </div>
}
