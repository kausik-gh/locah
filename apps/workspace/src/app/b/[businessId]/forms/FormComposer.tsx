'use client'

import { useState, useTransition, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { saveForm } from '../documents/actions'

type FieldKind = 'text' | 'textarea' | 'number' | 'date' | 'select' | 'checkbox' | 'radio' | 'file' | 'signature' | 'consent'

type FieldDraft = {
  key: string
  type: FieldKind
  label: string
  required: boolean
  help_text: string
  options: string
}

const KINDS: FieldKind[] = ['text', 'textarea', 'number', 'date', 'select', 'radio', 'checkbox', 'consent', 'file', 'signature']

function emptyField(): FieldDraft {
  return { key: 'field_name', type: 'text', label: 'Field label', required: false, help_text: '', options: 'Option A\nOption B' }
}

function toPayload(fields: FieldDraft[]) {
  return fields.map((field, order) => ({
    key: field.key.trim(),
    type: field.type,
    label: field.label.trim(),
    required: field.required,
    help_text: field.help_text.trim() || undefined,
    order,
    options: field.type === 'select' || field.type === 'radio'
      ? field.options.split('\n').map((line) => line.trim()).filter(Boolean)
      : [],
  }))
}

export function FormComposer({
  businessId,
  formId,
  initial,
}: {
  businessId: string
  formId?: string
  initial?: { title: string; kind: string; consent_text: string; guardian_required: boolean; fields: FieldDraft[] }
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [error, setError] = useState('')
  const [title, setTitle] = useState(initial?.title || '')
  const [kind, setKind] = useState(initial?.kind || 'intake')
  const [consentText, setConsentText] = useState(initial?.consent_text || '')
  const [guardianRequired, setGuardianRequired] = useState(initial?.guardian_required || false)
  const [fields, setFields] = useState<FieldDraft[]>(initial?.fields?.length ? initial.fields : [emptyField()])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    start(async () => {
      const body = {
        title: title.trim(),
        kind,
        fields: toPayload(fields),
        consent_text: consentText.trim() || null,
        guardian_required: guardianRequired,
      }
      const result = await saveForm(businessId, body, formId)
      if (!result.ok) { setError(result.error); return }
      router.push(`/b/${businessId}/forms`)
      router.refresh()
    })
  }

  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: '1rem' }}>
      <label>Form title<input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={160} /></label>
      <label>Type<select value={kind} onChange={(e) => setKind(e.target.value)}>
        {['intake', 'consent', 'agreement', 'report', 'generic'].map((value) => (
          <option key={value} value={value}>{value}</option>
        ))}
      </select></label>
      <label>Consent / terms text<textarea value={consentText} onChange={(e) => setConsentText(e.target.value)} rows={3} maxLength={5000} /></label>
      <label><input type="checkbox" checked={guardianRequired} onChange={(e) => setGuardianRequired(e.target.checked)} /> Require age confirmation and guardian relationship</label>
      <fieldset style={{ display: 'grid', gap: '.75rem', border: '1px solid var(--ws-border, #ddd)', padding: '1rem' }}>
        <legend>Fields</legend>
        {fields.map((field, index) => (
          <div key={index} style={{ display: 'grid', gap: '.5rem', paddingBottom: '.75rem', borderBottom: '1px solid #eee' }}>
            <label>Key<input value={field.key} onChange={(e) => {
              const next = [...fields]; next[index] = { ...field, key: e.target.value }; setFields(next)
            }} required pattern="[a-z][a-z0-9_]{0,59}" /></label>
            <label>Label<input value={field.label} onChange={(e) => {
              const next = [...fields]; next[index] = { ...field, label: e.target.value }; setFields(next)
            }} required maxLength={120} /></label>
            <label>Type<select value={field.type} onChange={(e) => {
              const next = [...fields]; next[index] = { ...field, type: e.target.value as FieldKind }; setFields(next)
            }}>{KINDS.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label><input type="checkbox" checked={field.required} onChange={(e) => {
              const next = [...fields]; next[index] = { ...field, required: e.target.checked }; setFields(next)
            }} /> Required</label>
            <label>Help text<input value={field.help_text} onChange={(e) => {
              const next = [...fields]; next[index] = { ...field, help_text: e.target.value }; setFields(next)
            }} maxLength={300} /></label>
            {field.type === 'select' || field.type === 'radio' ? (
              <label>Choices (one per line)<textarea value={field.options} onChange={(e) => {
                const next = [...fields]; next[index] = { ...field, options: e.target.value }; setFields(next)
              }} rows={3} required /></label>
            ) : null}
            <button type="button" className="ws-btn" disabled={fields.length <= 1} onClick={() => setFields(fields.filter((_, i) => i !== index))}>Remove field</button>
          </div>
        ))}
        <button type="button" className="ws-btn" onClick={() => setFields([...fields, emptyField()])} disabled={fields.length >= 30}>Add field</button>
      </fieldset>
      <button type="submit" className="ws-btn ws-btn--primary" disabled={pending}>
        {pending ? 'Saving…' : formId ? 'Save as new version' : 'Create form'}
      </button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  )
}
