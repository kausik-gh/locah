'use client'

/**
 * Schema-driven website-generation questionnaire (Doc 12 §12.7).
 *
 * Renders whatever the API's `GET /v1/b/{id}/website/questionnaire` returns —
 * this component knows question *kinds*, not business types. Every field is
 * optional; a field left untouched is simply absent from the submitted intake
 * and the backend fills it deterministically. There is no per-field AI, no
 * chat: one submit → one generation call.
 *
 * The same component is intended to mount in the Workspace "regenerate with
 * more detail" flow later; for now it is used only in /start.
 */

import React, { useMemo, useState } from 'react'

type Option = { value: string; label: string; primary?: string; accent?: string }
type TonePair = { id: string; left: string; right: string }
type Toggle = { id: string; label: string; default?: boolean }
type Field = { id: string; kind: string; label: string; example?: string; optional?: boolean }

type Question = {
  id: string
  kind: string
  label: string
  help?: string
  example?: string
  optional?: boolean
  options?: Option[]
  pairs?: TonePair[]
  toggles?: Toggle[]
  networks?: string[]
  fields?: Field[]
  item_label?: string
  max_items?: number
}

type Section = { id: string; title: string; subtitle?: string; questions: Question[] }
export type QuestionnaireSchema = { version: string; business_type: string; sections: Section[] }

type Answers = Record<string, unknown>

const teal = '#1c5f57'
const sans = 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif'

const card: React.CSSProperties = {
  padding: '1.25rem 1.35rem',
  borderRadius: '12px',
  border: '1px solid rgba(28,36,48,0.14)',
  background: 'rgba(255,255,255,0.72)',
  display: 'grid',
  gap: '0.7rem',
}
const labelStyle: React.CSSProperties = { fontWeight: 600, fontSize: '1rem' }
const helpStyle: React.CSSProperties = { fontFamily: sans, fontSize: '0.85rem', color: '#4c5967', lineHeight: 1.55 }
const exampleStyle: React.CSSProperties = {
  fontFamily: sans,
  fontSize: '0.8rem',
  color: '#6b7280',
  fontStyle: 'italic',
}
const input: React.CSSProperties = {
  fontFamily: sans,
  fontSize: '0.92rem',
  padding: '0.55rem 0.7rem',
  borderRadius: '8px',
  border: '1px solid rgba(28,36,48,0.2)',
  background: '#fff',
  width: '100%',
  boxSizing: 'border-box',
}

function Chip({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        fontFamily: sans,
        fontSize: '0.88rem',
        padding: '0.45rem 0.85rem',
        borderRadius: '999px',
        border: `1px solid ${active ? teal : 'rgba(28,36,48,0.22)'}`,
        background: active ? teal : 'transparent',
        color: active ? '#fff' : '#33404e',
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}

function AssetUpload({
  onUploaded,
  uploadStart,
  uploadFinish,
}: {
  onUploaded: (assetId: string) => void
  uploadStart: (
    mimeType: string,
    sizeBytes: number,
    originalFilename: string
  ) => Promise<{ ok: true; assetId: string; uploadUrl: string } | { ok: false; error: string }>
  uploadFinish: (assetId: string) => Promise<{ ok: boolean; error?: string }>
}) {
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pick = async (file: File) => {
    setError(null)
    if (file.size > 10 * 1024 * 1024) {
      setError('That image is over 10MB. Try a smaller one.')
      return
    }
    setBusy(true)
    try {
      const started = await uploadStart(file.type, file.size, file.name)
      if (!started.ok) return setError(started.error)
      // Straight to storage — the file body never passes through our servers.
      const put = await fetch(started.uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': file.type },
        body: file,
      })
      if (!put.ok) return setError(`Upload failed (${put.status}).`)
      const finished = await uploadFinish(started.assetId)
      if (!finished.ok) return setError(finished.error || 'Upload could not be confirmed.')
      onUploaded(started.assetId)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ marginTop: '0.6rem' }}>
      <label
        style={{
          display: 'inline-block',
          padding: '0.45rem 0.85rem',
          borderRadius: 8,
          border: `1px dashed ${teal}`,
          fontFamily: sans,
          fontSize: '0.85rem',
          color: teal,
          cursor: busy ? 'wait' : 'pointer',
        }}
      >
        {busy ? 'Uploading…' : done ? 'Uploaded ✓ — choose another' : 'Choose an image'}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          disabled={busy}
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void pick(file)
          }}
        />
      </label>
      {error ? (
        <div style={{ marginTop: '0.35rem', fontFamily: sans, fontSize: '0.8rem', color: '#8d2f24' }}>
          {error}
        </div>
      ) : null}
    </div>
  )
}

function QuestionView({
  q,
  value,
  set,
  onAsset,
  uploadStart,
  uploadFinish,
}: {
  q: Question
  value: unknown
  set: (v: unknown) => void
  onAsset: (assetId: string) => void
  uploadStart: (
    mimeType: string,
    sizeBytes: number,
    originalFilename: string
  ) => Promise<{ ok: true; assetId: string; uploadUrl: string } | { ok: false; error: string }>
  uploadFinish: (assetId: string) => Promise<{ ok: boolean; error?: string }>
}) {
  const header = (
    <div style={{ display: 'grid', gap: '0.25rem' }}>
      <span style={labelStyle}>{q.label}</span>
      {q.help ? <span style={helpStyle}>{q.help}</span> : null}
      {q.example ? <span style={exampleStyle}>e.g. {q.example}</span> : null}
    </div>
  )

  if (q.kind === 'single_select' || q.kind === 'asset_choice') {
    const v = typeof value === 'string' ? value : ''
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {(q.options || []).map((o) => (
            <Chip key={o.value} active={v === o.value} onClick={() => set(v === o.value ? '' : o.value)}>
              {o.label}
            </Chip>
          ))}
        </div>
        {q.kind === 'asset_choice' && v === 'upload' ? (
          <AssetUpload
            onUploaded={onAsset}
            uploadStart={uploadStart}
            uploadFinish={uploadFinish}
          />
        ) : null}
      </div>
    )
  }

  if (q.kind === 'palette_select') {
    const v = typeof value === 'string' ? value : ''
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(9rem, 1fr))', gap: '0.6rem' }}>
          {(q.options || []).map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => set(v === o.value ? '' : o.value)}
              style={{
                fontFamily: sans,
                fontSize: '0.83rem',
                textAlign: 'left',
                padding: '0.6rem',
                borderRadius: '10px',
                border: `2px solid ${v === o.value ? teal : 'rgba(28,36,48,0.15)'}`,
                background: '#fff',
                cursor: 'pointer',
                display: 'grid',
                gap: '0.4rem',
              }}
            >
              <span style={{ display: 'flex', gap: '0.3rem' }}>
                <span style={{ width: 20, height: 20, borderRadius: 4, background: o.primary }} />
                <span style={{ width: 20, height: 20, borderRadius: 4, background: o.accent }} />
              </span>
              {o.label}
            </button>
          ))}
        </div>
      </div>
    )
  }

  if (q.kind === 'slider_pair') {
    const v = (value && typeof value === 'object' ? value : {}) as Record<string, number>
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'grid', gap: '0.9rem', marginTop: '0.2rem' }}>
          {(q.pairs || []).map((p) => (
            <label key={p.id} style={{ display: 'grid', gap: '0.3rem', fontFamily: sans, fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', justifyContent: 'space-between', color: '#4c5967' }}>
                <span>{p.left}</span>
                <span>{p.right}</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={typeof v[p.id] === 'number' ? v[p.id] : 50}
                onChange={(e) => set({ ...v, [p.id]: Number(e.target.value) })}
              />
            </label>
          ))}
        </div>
      </div>
    )
  }

  if (q.kind === 'multi_toggle') {
    const v = (value && typeof value === 'object' ? value : {}) as Record<string, boolean>
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'grid', gap: '0.4rem', fontFamily: sans, fontSize: '0.9rem' }}>
          {(q.toggles || []).map((t) => {
            const checked = t.id in v ? v[t.id] : Boolean(t.default)
            return (
              <label key={t.id} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => set({ ...v, [t.id]: e.target.checked })}
                />
                {t.label}
              </label>
            )
          })}
        </div>
      </div>
    )
  }

  if (q.kind === 'social_links') {
    const v = (value && typeof value === 'object' ? value : {}) as Record<string, string>
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {(q.networks || []).map((n) => (
            <label key={n} style={{ display: 'grid', gap: '0.2rem', fontFamily: sans, fontSize: '0.82rem' }}>
              <span style={{ textTransform: 'capitalize', color: '#4c5967' }}>{n}</span>
              <input
                style={input}
                value={v[n] || ''}
                onChange={(e) => set({ ...v, [n]: e.target.value })}
                placeholder={n === 'instagram' ? '@yourshop' : ''}
              />
            </label>
          ))}
        </div>
      </div>
    )
  }

  if (q.kind === 'repeatable') {
    const rows = (Array.isArray(value) ? value : []) as Record<string, string>[]
    const max = q.max_items || 30
    const update = (i: number, fid: string, val: string) => {
      const next = rows.map((r, ri) => (ri === i ? { ...r, [fid]: val } : r))
      set(next)
    }
    return (
      <div style={card}>
        {header}
        <div style={{ display: 'grid', gap: '1rem' }}>
          {rows.map((row, i) => (
            <div
              key={i}
              style={{
                display: 'grid',
                gap: '0.5rem',
                padding: '0.8rem',
                borderRadius: '9px',
                border: '1px dashed rgba(28,36,48,0.2)',
              }}
            >
              {(q.fields || []).map((f) => (
                <label key={f.id} style={{ display: 'grid', gap: '0.2rem', fontFamily: sans, fontSize: '0.8rem' }}>
                  <span style={{ color: '#4c5967' }}>
                    {f.label}
                    {f.optional === false ? '' : ' — optional'}
                  </span>
                  <input
                    style={input}
                    value={row[f.id] || ''}
                    placeholder={f.example ? `e.g. ${f.example}` : ''}
                    onChange={(e) => update(i, f.id, e.target.value)}
                  />
                </label>
              ))}
              <button
                type="button"
                onClick={() => set(rows.filter((_, ri) => ri !== i))}
                style={{ ...input, width: 'auto', justifySelf: 'start', cursor: 'pointer', border: 'none', background: 'transparent', color: '#8d2f24', padding: '0.2rem 0' }}
              >
                Remove
              </button>
            </div>
          ))}
          {rows.length < max ? (
            <button
              type="button"
              onClick={() => set([...rows, {}])}
              style={{
                fontFamily: sans,
                fontSize: '0.85rem',
                padding: '0.5rem 0.9rem',
                borderRadius: '8px',
                border: `1px dashed ${teal}`,
                background: 'transparent',
                color: teal,
                cursor: 'pointer',
                justifySelf: 'start',
              }}
            >
              + Add {q.item_label || 'item'}
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  // default: text
  const v = typeof value === 'string' ? value : ''
  return (
    <div style={card}>
      {header}
      <input style={input} value={v} onChange={(e) => set(e.target.value)} placeholder={q.example ? `e.g. ${q.example}` : ''} />
    </div>
  )
}

export function WebsiteQuestionnaire({
  schema,
  action,
  skipHref,
  uploadStart,
  uploadFinish,
}: {
  schema: QuestionnaireSchema
  action: (intakeJson: string) => Promise<void>
  skipHref: string
  uploadStart: (
    mimeType: string,
    sizeBytes: number,
    originalFilename: string
  ) => Promise<{ ok: true; assetId: string; uploadUrl: string } | { ok: false; error: string }>
  uploadFinish: (assetId: string) => Promise<{ ok: boolean; error?: string }>
}) {
  const [answers, setAnswers] = useState<Answers>({})
  const [submitting, setSubmitting] = useState(false)

  const answeredCount = useMemo(
    () => Object.values(answers).filter((v) => v !== '' && v != null && !(Array.isArray(v) && v.length === 0)).length,
    [answers]
  )

  const set = (id: string, v: unknown) => setAnswers((a) => ({ ...a, [id]: v }))

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    // Prune empty answers so the backend deterministic fallback owns them.
    const clean: Answers = {}
    for (const [k, v] of Object.entries(answers)) {
      if (v === '' || v == null) continue
      if (Array.isArray(v)) {
        const rows = (v as Record<string, string>[])
          .map((r) => Object.fromEntries(Object.entries(r).filter(([, x]) => String(x).trim())))
          .filter((r) => Object.keys(r).length > 0)
        if (rows.length) clean[k] = rows
        continue
      }
      if (typeof v === 'object') {
        const entries = Object.entries(v as Record<string, unknown>).filter(([, x]) => x !== '' && x != null)
        if (entries.length) clean[k] = Object.fromEntries(entries)
        continue
      }
      clean[k] = v
    }
    await action(JSON.stringify(clean))
  }

  return (
    <form onSubmit={onSubmit} style={{ display: 'grid', gap: '1.75rem' }}>
      {schema.sections.map((s) => (
        <section key={s.id} style={{ display: 'grid', gap: '0.9rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.3rem' }}>{s.title}</h2>
            {s.subtitle ? (
              <p style={{ margin: '0.3rem 0 0', ...helpStyle }}>{s.subtitle}</p>
            ) : null}
          </div>
          {s.questions.map((q) => (
            <QuestionView
              key={q.id}
              q={q}
              value={answers[q.id]}
              set={(v) => set(q.id, v)}
              onAsset={(assetId) => set(`${q.id}_asset_id`, assetId)}
              uploadStart={uploadStart}
              uploadFinish={uploadFinish}
            />
          ))}
        </section>
      ))}

      <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          type="submit"
          disabled={submitting}
          style={{
            fontFamily: sans,
            fontWeight: 600,
            fontSize: '0.95rem',
            padding: '0.7rem 1.5rem',
            borderRadius: '8px',
            border: 'none',
            background: teal,
            color: '#fff',
            cursor: submitting ? 'wait' : 'pointer',
          }}
        >
          {submitting
            ? 'Building your site…'
            : answeredCount > 0
              ? `Build my site with these ${answeredCount} answer${answeredCount === 1 ? '' : 's'}`
              : 'Build my site'}
        </button>
        <a href={skipHref} style={{ fontFamily: sans, fontSize: '0.9rem', color: teal }}>
          Skip — just use my business details
        </a>
      </div>
    </form>
  )
}
