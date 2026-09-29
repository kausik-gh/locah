'use client'

import { useState, useTransition, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { createTemplate } from './actions'

export function TemplateComposer({ businessId }: { businessId: string }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [error, setError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setError('')
    start(async () => {
      const result = await createTemplate(businessId, form)
      if (!result.ok) { setError(result.error); return }
      router.refresh()
    })
  }
  return <form onSubmit={submit} style={{ display: 'grid', gap: '.75rem' }}>
    <label>Title<input name="title" required maxLength={160} placeholder="Service agreement" /></label>
    <label>Type<select name="kind" defaultValue="agreement">
      {['agreement','consent','intake','certificate','report','generic'].map(value =>
        <option key={value} value={value}>{value}</option>)}</select></label>
    <label>What is it for?<input name="description" maxLength={1000} placeholder="Reusable terms for new clients" /></label>
    <label>Template wording<textarea name="body" required rows={5} placeholder="Write the terms or instructions here…" /></label>
    <button className="ws-btn ws-btn--primary" disabled={pending} type="submit">{pending ? 'Saving…' : 'Save template'}</button>
    {error ? <p role="alert">{error}</p> : null}
  </form>
}
