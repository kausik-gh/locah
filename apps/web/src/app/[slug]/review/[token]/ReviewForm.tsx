'use client'

import { useState, type FormEvent } from 'react'
import { platformUrl } from '@platform/config'
import type { ReviewerView } from '@/lib/public-reviews'

type PhotoInput = { media_type: string; data_base64: string }

async function photoInput(file: File): Promise<PhotoInput> {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Choose a JPEG, PNG or WebP photo.')
  if (file.size > 1_500_000) throw new Error('Each photo must be under 1.5 MB.')
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('The photo could not be read.'))
    reader.readAsDataURL(file)
  })
  return { media_type: file.type, data_base64: data.split(',')[1] || '' }
}

export function ReviewForm({ initial, slug, token }: { initial: ReviewerView; slug: string; token: string }) {
  const [view, setView] = useState(initial)
  const [rating, setRating] = useState(initial.review?.rating || 0)
  const [body, setBody] = useState(initial.review?.body || '')
  const [files, setFiles] = useState<File[]>([])
  const [removed, setRemoved] = useState<string[]>([])
  const [appeal, setAppeal] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const url = `${platformUrl('api')}/v1/public/websites/${encodeURIComponent(slug)}/review/${encodeURIComponent(token)}`

  async function call(path: string, method: 'POST' | 'PUT', payload?: unknown) {
    setBusy(true)
    setError('')
    try {
      const res = await fetch(`${url}${path}`, {
        method,
        headers: payload ? { 'Content-Type': 'application/json' } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
        cache: 'no-store',
      })
      const json = await res.json()
      if (!res.ok) throw new Error(
        typeof json.error?.message === 'string' ? json.error.message
          : typeof json.detail === 'string' ? json.detail
            : 'This request could not be saved. Please try again.',
      )
      setView(json.data as ReviewerView)
      setFiles([])
      setRemoved([])
      setSaved(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!rating) { setError('Choose a star rating.'); return }
    if (files.length + (view.review?.photos.length || 0) - removed.length > 3) {
      setError('You can share up to three photos.'); return
    }
    try {
      const photos = await Promise.all(files.map(photoInput))
      const payload = view.review
        ? { rating, body: body.trim() || null, photos, remove_photo_ids: removed }
        : { rating, body: body.trim() || null, photos }
      await call('', view.review ? 'PUT' : 'POST', payload)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The photos could not be read.')
    }
  }

  if (view.state === 'declined') return <p className="ls-review-notice">No problem. We won’t ask you to review this interaction again.</p>
  if (view.state === 'expired') return <p className="ls-review-notice">This review invitation has expired.</p>
  if (view.review?.status === 'removed') return (
    <div className="ls-review-form">
      <p className="ls-review-notice">This review was removed by moderation. {view.review.appeal ? `Appeal: ${view.review.appeal.status}.` : 'You may appeal once.'}</p>
      {view.review.can_appeal ? (
        <form onSubmit={(event) => { event.preventDefault(); void call('/appeal', 'POST', { note: appeal }) }}>
          <label htmlFor="review-appeal">Why should it be restored?</label>
          <textarea id="review-appeal" value={appeal} onChange={(event) => setAppeal(event.target.value)} minLength={5} maxLength={1000} required />
          <button type="submit" className="ls-btn" disabled={busy}>Send appeal</button>
        </form>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  )

  return (
    <div className="ls-review-form">
      {saved ? <p className="ls-review-success" role="status">Your review has been saved. You can update it here if anything changes.</p> : null}
      {view.review ? <p className="ls-review-notice">Your review is live. Only you can change your rating and words.</p> : null}
      <form onSubmit={(event) => { void submit(event) }}>
        <fieldset className="ls-review-stars">
          <legend>Your rating</legend>
          {[1, 2, 3, 4, 5].map((star) => (
            <label key={star}>
              <input type="radio" name="rating" value={star} checked={rating === star} onChange={() => setRating(star)} required />
              <span aria-hidden="true">{star <= rating ? '★' : '☆'}</span><span className="ls-sr-only">{star} stars</span>
            </label>
          ))}
        </fieldset>
        <label htmlFor="review-body">Your experience <span>(optional)</span></label>
        <textarea id="review-body" value={body} onChange={(event) => setBody(event.target.value)} maxLength={2000} rows={5} placeholder="What went well? What could be better?" />
        {view.review?.photos.length ? (
          <fieldset className="ls-review-existing"><legend>Your photos</legend>
            {view.review.photos.map((id) => <label key={id}><input type="checkbox" checked={removed.includes(id)} onChange={() => setRemoved((ids) => ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id])} /> Remove photo</label>)}
          </fieldset>
        ) : null}
        <label htmlFor="review-photos">Add photos <span>(optional, up to 3 JPEG, PNG or WebP; 1.5 MB each)</span></label>
        <input id="review-photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} />
        {error ? <p className="ls-review-error" role="alert">{error}</p> : null}
        <button type="submit" className="ls-btn" disabled={busy}>{busy ? 'Saving…' : view.review ? 'Update my review' : 'Post my review'}</button>
      </form>
      {!view.review ? <button type="button" className="ls-review-decline" disabled={busy} onClick={() => { void call('/decline', 'POST') }}>No thanks</button> : null}
      <p className="ls-review-privacy">Your rating and words will be public. Your phone number will not be shown.</p>
    </div>
  )
}
