'use client'

import { useState, useTransition } from 'react'
import { LocalTime } from '@/components/LocalTime'
import { assignRole, changeStatus, newJoinLink, withdrawInvitation } from './team-actions'
import type { Invited, Member, RoleCatalogue, RoleOption } from './types'

const initial = (name: string) => (name.trim()[0] || '?').toUpperCase()

export function whatsappShare(text: string) {
  return `https://wa.me/?text=${encodeURIComponent(text)}`
}

/** Members and people waiting to join, each with what the owner can do next. */
export function TeamBoard({
  businessId,
  members,
  invited,
  roles,
}: {
  businessId: string
  members: Member[]
  invited: Invited[]
  roles: RoleCatalogue | null
}) {
  return (
    <>
      <section aria-labelledby="members-h">
        <h2 className="bos-section__title" id="members-h">
          People <span>{members.length}</span>
        </h2>
        <ul className="bos-people">
          {members.map((m) => (
            <MemberRow key={m.id} businessId={businessId} member={m} roles={roles} />
          ))}
        </ul>
      </section>
      <section className="bos-section" aria-labelledby="invited-h">
        <h2 className="bos-section__title" id="invited-h">
          Waiting to join <span>{invited.length}</span>
        </h2>
        {invited.length === 0 ? (
          <div className="bos-empty">
            Nobody is waiting. When you add a person, they appear here until they open their join link.
          </div>
        ) : (
          <ul className="bos-people">
            {invited.map((i) => (
              <InvitedRow key={i.invitation_id} businessId={businessId} person={i} />
            ))}
          </ul>
        )}
      </section>
    </>
  )
}

function MemberRow({ businessId, member, roles }: { businessId: string; member: Member; roles: RoleCatalogue | null }) {
  const [editing, setEditing] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const isOwner = member.role.key === 'owner'
  const where =
    member.locations.length > 0 ? member.locations.map((l) => l.name).join(', ') : 'All locations'

  const act = (fn: () => Promise<{ ok: boolean; message?: string }>, done: string) => {
    setMsg(null)
    start(async () => {
      const r = await fn()
      setMsg(r.ok ? { text: done } : { text: ('message' in r && r.message) || 'That did not work.', bad: true })
    })
  }

  return (
    <li className={`bos-person${member.status !== 'active' ? ' is-muted' : ''}`}>
      <div className="bos-person__main">
        <span className="bos-avatar" aria-hidden>
          {initial(member.name)}
        </span>
        <div>
          <p className="bos-person__name">
            {member.name}
            {member.status !== 'active' ? <span className="bos-tag">{member.status}</span> : null}
          </p>
          <p className="bos-person__meta">{member.email}</p>
        </div>
      </div>
      <div className="bos-person__role">
        <strong>{member.role.label}</strong>
        <span>{isOwner ? 'Everything' : where}</span>
      </div>
      {!isOwner ? (
        <div className="bos-person__actions">
          <button type="button" className="btn-quiet" onClick={() => setEditing((v) => !v)} disabled={pending}>
            {editing ? 'Close' : 'Change role'}
          </button>
          <button
            type="button"
            className="btn-quiet"
            disabled={pending}
            onClick={() =>
              act(
                () => changeStatus(businessId, member.id, member.status === 'active' ? 'suspend' : 'reactivate'),
                member.status === 'active' ? 'Paused. They cannot sign in to this business.' : 'Back on the team.',
              )
            }
          >
            {member.status === 'active' ? 'Pause access' : 'Restore access'}
          </button>
          {confirmRemove ? (
            <>
              <button
                type="button"
                className="btn-danger"
                disabled={pending}
                onClick={() => act(() => changeStatus(businessId, member.id, 'remove'), 'Removed from the team.')}
              >
                Remove {member.name}
              </button>
              <button type="button" className="btn-quiet" onClick={() => setConfirmRemove(false)}>
                Keep
              </button>
            </>
          ) : (
            <button type="button" className="btn-quiet" onClick={() => setConfirmRemove(true)} disabled={pending}>
              Remove
            </button>
          )}
        </div>
      ) : null}
      {editing && roles ? (
        <RoleEditor
          roles={roles}
          current={member}
          pending={pending}
          onSave={(role, locations) =>
            act(async () => {
              const r = await assignRole(businessId, member.id, role, locations)
              if (r.ok) setEditing(false)
              return r
            }, 'Role changed. It applies the next time they open Workspace.')
          }
        />
      ) : null}
      {msg ? (
        <p className={`bos-status bos-person__msg${msg.bad ? ' bos-error' : ''}`} role="status">
          {msg.text}
        </p>
      ) : null}
    </li>
  )
}

/** Pick a role (template or custom) and, for location roles, where. */
export function RoleEditor({
  roles,
  current,
  pending,
  onSave,
  saveLabel = 'Save role',
}: {
  roles: RoleCatalogue
  current?: Member
  pending: boolean
  onSave: (role: string, locations: string[]) => void
  saveLabel?: string
}) {
  const options: RoleOption[] = [...roles.templates, ...roles.custom]
  const [role, setRole] = useState(current?.role.key && options.some((o) => o.key === current.role.key)
    ? current.role.key
    : options[0]?.key ?? '')
  const [locs, setLocs] = useState<string[]>(
    current?.locations.length ? current.locations.map((l) => l.id) : roles.locations.slice(0, 1).map((l) => l.id),
  )
  const chosen = options.find((o) => o.key === role)
  const needsLocations = chosen?.scope === 'location'
  return (
    <div className="bos-role-editor">
      <fieldset className="bos-role-options">
        <legend className="bos-label">Role</legend>
        {options.map((o) => (
          <label key={o.key} className={`bos-role-option${role === o.key ? ' is-on' : ''}`}>
            <input type="radio" name={`role-${current?.id ?? 'new'}`} value={o.key} checked={role === o.key}
              onChange={() => setRole(o.key)} />
            <span>
              <strong>{o.label}</strong>
              <small>{o.does ?? (o.based_on_label ? `Custom, based on ${o.based_on_label}` : 'Custom role')}</small>
              <small className="bos-role-option__home">Home: {o.home ?? 'Their work today'}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {needsLocations ? (
        <fieldset className="bos-role-locations">
          <legend className="bos-label">Where they work</legend>
          <div className="bos-choices">
            {roles.locations.map((l) => (
              <label key={l.id} className="bos-choice">
                <input
                  type="checkbox"
                  checked={locs.includes(l.id)}
                  onChange={() => setLocs((s) => (s.includes(l.id) ? s.filter((x) => x !== l.id) : [...s, l.id]))}
                />
                {l.name}
              </label>
            ))}
          </div>
          <p className="bos-hint">They only see orders, bookings and stock at these locations.</p>
        </fieldset>
      ) : (
        <p className="bos-hint">{chosen ? `${chosen.label} works across ${chosen.scope_words.toLowerCase()}.` : ''}</p>
      )}
      <button
        type="button"
        disabled={pending || !role || (needsLocations && locs.length === 0)}
        onClick={() => onSave(role, needsLocations ? locs : [])}
      >
        {pending ? 'Saving…' : saveLabel}
      </button>
    </div>
  )
}

function InvitedRow({ businessId, person }: { businessId: string; person: Invited }) {
  const [link, setLink] = useState<string | null>(null)
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)

  const makeLink = () =>
    start(async () => {
      setMsg(null)
      const r = await newJoinLink(businessId, person.invitation_id)
      if (r.ok && r.data) {
        const url = `${window.location.origin}${r.data.join_path}`
        setLink(url)
        try {
          await navigator.clipboard.writeText(url)
          setMsg({ text: 'New link copied. Any earlier link for them has stopped working.' })
        } catch {
          setMsg({ text: 'New link ready below. Any earlier link for them has stopped working.' })
        }
      } else setMsg({ text: (!r.ok && r.message) || 'Could not make a link.', bad: true })
    })

  return (
    <li className="bos-person">
      <div className="bos-person__main">
        <span className="bos-avatar is-waiting" aria-hidden>
          {initial(person.name)}
        </span>
        <div>
          <p className="bos-person__name">{person.name}</p>
          <p className="bos-person__meta">{person.email}</p>
        </div>
      </div>
      <div className="bos-person__role">
        <strong>{person.role_label}</strong>
        <span>
          {person.expired ? 'Link expired' : <>Link valid until <LocalTime value={person.expires_at} mode="date" /></>}
        </span>
      </div>
      <div className="bos-person__actions">
        <button type="button" className="btn-quiet" onClick={makeLink} disabled={pending}>
          {person.expired ? 'Make a new link' : 'Copy a new link'}
        </button>
        <button
          type="button"
          className="btn-quiet"
          disabled={pending}
          onClick={() =>
            start(async () => {
              const r = await withdrawInvitation(businessId, person.invitation_id)
              setMsg(r.ok ? { text: 'Withdrawn.' } : { text: r.message, bad: true })
            })
          }
        >
          Withdraw
        </button>
      </div>
      {link ? (
        <div className="bos-joinlink">
          <input readOnly value={link} aria-label={`Join link for ${person.name}`} onFocus={(e) => e.target.select()} />
          <a
            className="btn-ghost btn"
            href={whatsappShare(`Hi ${person.name}, here is your link to join us on LOCAH as ${person.role_label}: ${link}`)}
            target="_blank"
            rel="noreferrer"
          >
            Share on WhatsApp
          </a>
        </div>
      ) : null}
      {msg ? (
        <p className={`bos-status bos-person__msg${msg.bad ? ' bos-error' : ''}`} role="status">
          {msg.text}
        </p>
      ) : null}
    </li>
  )
}
