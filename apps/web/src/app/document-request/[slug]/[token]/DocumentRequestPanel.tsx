'use client'

import { useMemo, useRef, useState, type FormEvent } from 'react'
import { platformUrl } from '@platform/config'
import type { DocumentRequestView, PublicFormField } from '@/lib/public-documents'

type Answers = Record<string, string | number | boolean>

function apiBase(slug: string, token: string) {
  return `${platformUrl('api')}/v1/public/documents/${encodeURIComponent(slug)}/${encodeURIComponent(token)}`
}

async function uploadFile(slug: string, token: string, fieldKey: string, file: File) {
  const body = new FormData()
  body.set('field_key', fieldKey)
  body.set('file', file)
  const res = await fetch(`${apiBase(slug, token)}/upload`, { method: 'POST', body, cache: 'no-store' })
  const json = await res.json()
  if (!res.ok) {
    throw new Error(json?.error?.message || json?.detail?.message || 'Upload failed')
  }
  return String(json.data.id)
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: PublicFormField
  value: unknown
  onChange: (next: unknown) => void
}) {
  const id = `field-${field.key}`
  if (field.type === 'textarea') {
    return <textarea id={id} required={field.required} value={String(value || '')} onChange={(e) => onChange(e.target.value)} rows={4} maxLength={4000} />
  }
  if (field.type === 'number') {
    return <input id={id} type="number" required={field.required} value={value === undefined || value === '' ? '' : Number(value)} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
  }
  if (field.type === 'date') {
    return <input id={id} type="date" required={field.required} value={String(value || '')} onChange={(e) => onChange(e.target.value)} />
  }
  if (field.type === 'select' || field.type === 'radio') {
    return (
      <select id={id} required={field.required} value={String(value || '')} onChange={(e) => onChange(e.target.value)}>
        <option value="" disabled>Choose…</option>
        {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    )
  }
  if (field.type === 'checkbox' || field.type === 'consent') {
    return <input id={id} type="checkbox" required={field.required} checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
  }
  if (field.type === 'file') {
    return <input id={id} type="file" required={field.required && !value} accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e) => onChange(e.target.files?.[0] || null)} />
  }
  return <input id={id} type="text" required={field.required} value={String(value || '')} onChange={(e) => onChange(e.target.value)} maxLength={500} />
}

export function DocumentRequestPanel({ initial, slug, token }: { initial: DocumentRequestView; slug: string; token: string }) {
  const [view, setView] = useState(initial)
  const [answers, setAnswers] = useState<Answers>({})
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [signerName, setSignerName] = useState('')
  const [signatureMode, setSignatureMode] = useState<'typed' | 'drawn'>('typed')
  const [ageConfirmed, setAgeConfirmed] = useState(false)
  const [guardianRelationship, setGuardianRelationship] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(view.status === 'fulfilled')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const strokes = useRef<number[][][]>([])
  const current = useRef<number[][]>([])

  const fields = useMemo(() => {
    const list = view.form?.fields || []
    return [...list].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).filter((f) => f.type !== 'signature')
  }, [view.form?.fields])
  const needsSignature = (view.form?.fields || []).some((f) => f.type === 'signature')

  function pointer(event: React.PointerEvent<HTMLCanvasElement>, start: boolean) {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height
    if (start) {
      drawing.current = true
      current.current = [[x, y]]
    } else if (drawing.current) {
      current.current.push([x, y])
    }
  }

  function endStroke() {
    if (!drawing.current) return
    drawing.current = false
    if (current.current.length >= 2) strokes.current.push(current.current)
    current.current = []
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.strokeStyle = '#111'
    ctx.lineWidth = 2
    const stroke = strokes.current[strokes.current.length - 1]
    ctx.beginPath()
    stroke.forEach(([x, y], i) => {
      const px = x * canvas.width
      const py = y * canvas.height
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    })
    ctx.stroke()
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload: Answers = { ...answers }
      for (const field of fields) {
        if (field.type === 'file') {
          const file = files[field.key]
          if (file) payload[field.key] = await uploadFile(slug, token, field.key, file)
        }
      }
      let signature: { kind: 'typed' | 'drawn'; value: string | number[][][] } | null = null
      if (needsSignature) {
        if (signatureMode === 'typed') {
          signature = { kind: 'typed', value: signerName.trim() }
        } else {
          if (!strokes.current.length) throw new Error('Draw your signature on the pad.')
          signature = { kind: 'drawn', value: strokes.current }
        }
      }
      const res = await fetch(`${apiBase(slug, token)}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: payload,
          signer_name: signerName.trim(),
          signature,
          age_confirmed: ageConfirmed,
          guardian_relationship: guardianRelationship.trim() || null,
        }),
        cache: 'no-store',
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json?.error?.message || json?.detail?.message || 'Could not submit')
      setDone(true)
      setView({ ...view, status: 'fulfilled' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const fileInput = (event.currentTarget.elements.namedItem('requested_file') as HTMLInputElement)?.files?.[0]
      if (!fileInput) throw new Error('Choose a file to upload.')
      await uploadFile(slug, token, 'requested_file', fileInput)
      setDone(true)
      setView({ ...view, status: 'fulfilled' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  if (done || view.status === 'fulfilled') {
    return (
      <div className="ls-review-form" role="status">
        <p className="ls-review-success">Thank you — your {view.request_type === 'form' ? 'form' : 'document'} was received.</p>
        <p className="ls-review-notice">You can close this page. The link cannot be reused for other requests.</p>
      </div>
    )
  }

  if (view.request_type === 'upload') {
    return (
      <form className="ls-review-form" onSubmit={(e) => { void submitUpload(e) }}>
        <p>{view.title}</p>
        <label htmlFor="requested_file">Upload PDF or image (max 5 MB)</label>
        <input id="requested_file" name="requested_file" type="file" required accept=".pdf,image/jpeg,image/png,image/webp" />
        <button type="submit" className="ls-btn" disabled={busy}>{busy ? 'Uploading…' : 'Send file'}</button>
        {error ? <p role="alert">{error}</p> : null}
      </form>
    )
  }

  return (
    <form className="ls-review-form" onSubmit={(e) => { void submitForm(e) }}>
      <p>{view.title}</p>
      {view.form?.consent_text ? <p className="ls-review-notice">{view.form.consent_text}</p> : null}
      {fields.map((field) => (
        <label key={field.key} htmlFor={`field-${field.key}`}>
          {field.label}{field.required ? ' *' : ''}
          {field.help_text ? <small>{field.help_text}</small> : null}
          <FieldInput
            field={field}
            value={field.type === 'file' ? files[field.key] : answers[field.key]}
            onChange={(next) => {
              if (field.type === 'file') setFiles({ ...files, [field.key]: next as File | null })
              else setAnswers({ ...answers, [field.key]: next as string | number | boolean })
            }}
          />
        </label>
      ))}
      <label htmlFor="signer-name">Your full name *</label>
      <input id="signer-name" required maxLength={160} value={signerName} onChange={(e) => setSignerName(e.target.value)} />
      {view.form?.guardian_required ? (
        <>
          <label><input type="checkbox" checked={ageConfirmed} onChange={(e) => setAgeConfirmed(e.target.checked)} required /> I confirm the signer is 18 or older, or a guardian is completing this form</label>
          <label htmlFor="guardian-rel">Guardian relationship (if under 18) *</label>
          <input id="guardian-rel" maxLength={120} value={guardianRelationship} onChange={(e) => setGuardianRelationship(e.target.value)} required={view.form.guardian_required && !ageConfirmed} />
        </>
      ) : null}
      {needsSignature ? (
        <fieldset>
          <legend>Signature *</legend>
          <label><input type="radio" name="sig-mode" checked={signatureMode === 'typed'} onChange={() => setSignatureMode('typed')} /> Type my name</label>
          <label><input type="radio" name="sig-mode" checked={signatureMode === 'drawn'} onChange={() => setSignatureMode('drawn')} /> Draw signature</label>
          {signatureMode === 'drawn' ? (
            <canvas
              ref={canvasRef}
              width={320}
              height={120}
              style={{ border: '1px solid #ccc', touchAction: 'none', width: '100%', maxWidth: 420 }}
              onPointerDown={(e) => { canvasRef.current?.setPointerCapture(e.pointerId); pointer(e, true) }}
              onPointerMove={(e) => pointer(e, false)}
              onPointerUp={endStroke}
              onPointerLeave={endStroke}
            />
          ) : (
            <p className="ls-hint">Your typed name must match the full name above.</p>
          )}
        </fieldset>
      ) : null}
      <button type="submit" className="ls-btn" disabled={busy}>{busy ? 'Submitting…' : 'Submit'}</button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  )
}
