'use client'

import Link from 'next/link'
import { useState, useTransition } from 'react'
import { RoleEditor, whatsappShare } from '../TeamBoard'
import { addPerson } from '../team-actions'
import type { RoleCatalogue } from '../types'

export function AddPersonForm({
  businessId,
  businessName,
  roles,
}: {
  businessId: string
  businessName: string
  roles: RoleCatalogue
}) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<{ url: string; name: string; role: string; home: string } | null>(null)

  if (done) {
    const message = `Hi ${done.name}, you have been added to ${businessName} on LOCAH as ${done.role}. Open this link to create your login: ${done.url}`
    return (
      <section className="bos-card bos-joined" aria-labelledby="link-h">
        <h2 id="link-h">Send {done.name} this link</h2>
        <p className="bos-hint">
          They open it, create a login with <strong>{email}</strong>, and land on their home: “{done.home}”. The link
          works once and expires in 48 hours.
        </p>
        <div className="bos-joinlink">
          <input readOnly value={done.url} aria-label="Join link" onFocus={(e) => e.target.select()} />
          <button
            type="button"
            className="btn-ghost"
            onClick={() => navigator.clipboard?.writeText(done.url).catch(() => undefined)}
          >
            Copy
          </button>
          <a className="btn" href={whatsappShare(message)} target="_blank" rel="noreferrer">
            Share on WhatsApp
          </a>
        </div>
        <p style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <Link href={`/b/${businessId}/team`}>Back to team</Link>
          <button type="button" className="btn-quiet" onClick={() => { setDone(null); setName(''); setEmail('') }}>
            Add another person
          </button>
        </p>
      </section>
    )
  }

  return (
    <div className="bos-works">
      <section className="bos-card" aria-labelledby="who-h">
        <h2 id="who-h">Who</h2>
        <div className="bos-form-grid">
          <label>
            <span className="bos-label">Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" required />
          </label>
          <label>
            <span className="bos-label">Email they will sign in with</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" required />
          </label>
        </div>
      </section>
      <section className="bos-card" aria-labelledby="role-h">
        <h2 id="role-h">What they do</h2>
        <RoleEditor
          roles={roles}
          pending={pending}
          saveLabel="Add and make a join link"
          onSave={(role, locations) => {
            setError(null)
            if (!name.trim() || !email.includes('@')) {
              setError('Enter their name and the email they will sign in with.')
              return
            }
            start(async () => {
              const r = await addPerson(businessId, { name: name.trim(), email: email.trim(), role, location_ids: locations })
              if (r.ok && r.data) {
                const opt = [...roles.templates, ...roles.custom].find((o) => o.key === role)
                setDone({
                  url: `${window.location.origin}${r.data.join_path}`,
                  name: name.trim(),
                  role: opt?.label ?? 'a team member',
                  home: opt?.home ?? 'their work today',
                })
              } else setError((!r.ok && r.message) || 'That did not save.')
            })
          }}
        />
        {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
      </section>
    </div>
  )
}
