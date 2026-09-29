'use client'

import { useState, useTransition, type FormEvent } from 'react'
import { platformUrl } from '@platform/config'
import { createRequest, createFileAccess } from './actions'

type FormOption = { id: string; title: string; current_version: number }

export function RequestComposer({ businessId, kind, forms = [] }: {
  businessId: string; kind: 'form' | 'upload'; forms?: FormOption[]
}) {
  const [pending, start] = useTransition()
  const [error, setError] = useState('')
  const [link, setLink] = useState('')
  const [copied, setCopied] = useState(false)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setError('')
    start(async () => {
      const result = await createRequest(businessId, {
        request_type: kind,
        title: String(values.get('title') || '').trim(),
        form_id: kind === 'form' ? String(values.get('formId') || '') : null,
        related_type: String(values.get('relatedType') || 'general'),
        related_id: String(values.get('relatedId') || '').trim() || null,
        customer_contact_id: String(values.get('contactId') || '').trim() || null,
        days_valid: Number(values.get('daysValid') || 7),
      })
      if (!result.ok) { setError(result.error); return }
      setLink(platformUrl('web', String(result.data.public_path || '')))
      setCopied(false)
    })
  }
  return <div>
    <form onSubmit={submit} style={{ display: 'grid', gap: '.75rem' }}>
      <label>Request title<input name="title" required maxLength={160}
        placeholder={kind === 'form' ? 'Please complete your intake form' : 'Please upload your ID'} /></label>
      {kind === 'form' ? <label>Form<select name="formId" required defaultValue="">
        <option value="" disabled>Choose a form</option>
        {forms.map(form => <option key={form.id} value={form.id}>{form.title} · v{form.current_version}</option>)}
      </select></label> : null}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '.75rem' }}>
        <label>Attach to<select name="relatedType" defaultValue="general">
          {['general','customer','quote','project','job','booking','membership','academic_student','order','supplier'].map(value =>
            <option key={value} value={value}>{value.replace('_', ' ')}</option>)}</select></label>
        <label>Related record ID<input name="relatedId" placeholder="UUID, if attaching" /></label>
      </div>
      <label>Customer contact ID (optional)<input name="contactId" placeholder="UUID" /></label>
      <label>Link expires in<select name="daysValid" defaultValue="7">
        <option value="1">1 day</option><option value="7">7 days</option>
        <option value="14">14 days</option><option value="30">30 days</option>
      </select></label>
      <button type="submit" className="ws-btn ws-btn--primary" disabled={pending || (kind === 'form' && !forms.length)}>
        {pending ? 'Creating secure link…' : 'Create request link'}
      </button>
    </form>
    {error ? <p role="alert">{error}</p> : null}
    {link ? <div role="status" style={{ marginTop: '1rem', overflowWrap: 'anywhere' }}>
      <strong>Share this private link once.</strong><p><a href={link} target="_blank" rel="noreferrer">{link}</a></p>
      <button type="button" className="ws-btn" onClick={() => { void navigator.clipboard.writeText(link).then(() => setCopied(true)) }}>
        {copied ? 'Copied' : 'Copy link'}
      </button>
      <p style={{ fontSize: '.8rem' }}>The link is shown now, not stored in the Workspace. Share it through your approved message channel.</p>
    </div> : null}
  </div>
}

export function FileAccessButton({ businessId, fileId }: { businessId: string; fileId: string }) {
  const [pending, start] = useTransition()
  const [error, setError] = useState('')
  function open() {
    start(async () => {
      const result = await createFileAccess(businessId, fileId)
      if (!result.ok) { setError(result.error); return }
      const url = platformUrl('api', String(result.data.download_path || ''))
      window.open(url, '_blank', 'noopener,noreferrer')
    })
  }
  return <span><button type="button" className="ws-btn" disabled={pending} onClick={open}>
    {pending ? 'Preparing…' : 'Download file'}</button>{error ? <small role="alert">{error}</small> : null}</span>
}
