'use client'

import { useMemo, useState, useTransition } from 'react'
import { removeCustomRole, saveCustomRole } from '../team-actions'
import { groupPermissions, type RoleCatalogue, type RoleOption } from '../types'

function RoleCard({ role, words, children }: { role: RoleOption; words: Record<string, string>; children?: React.ReactNode }) {
  const groups = groupPermissions(role.permissions, words)
  return (
    <article className="bos-tool bos-rolecard">
      <div className="bos-tool__head">
        <h3>{role.label}</h3>
        <span className="bos-tag">{role.scope_words}</span>
      </div>
      <p className="bos-tool__does">
        {role.does ?? (role.based_on_label ? `Custom role based on ${role.based_on_label}` : 'Custom role')}
      </p>
      <p className="bos-tool__why">
        <span>Home screen</span>
        {role.home ?? 'Their work today'}
      </p>
      <details className="bos-more">
        <summary className="bos-hint">What they can do ({role.permissions.length})</summary>
        <div className="bos-permgroups">
          {groups.map((g) => (
            <div key={g.area}>
              <strong>{g.label}</strong>
              <ul>{g.items.map((i) => <li key={i.id}>{i.label}</li>)}</ul>
            </div>
          ))}
        </div>
      </details>
      {children}
    </article>
  )
}

export function RolesBoard({ businessId, roles }: { businessId: string; roles: RoleCatalogue }) {
  const [editing, setEditing] = useState<RoleOption | 'new' | null>(null)
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)

  return (
    <>
      <section aria-labelledby="builtin-h">
        <h2 className="bos-section__title" id="builtin-h">
          Ready-made roles <span>{roles.templates.length + 1}</span>
        </h2>
        <div className="bos-grid">
          <RoleCard role={roles.owner} words={roles.permission_words} />
          {roles.templates.map((r) => (
            <RoleCard key={r.key} role={r} words={roles.permission_words} />
          ))}
        </div>
      </section>

      <section className="bos-section" aria-labelledby="custom-h">
        <h2 className="bos-section__title" id="custom-h">
          Your roles <span>{roles.custom.length}</span>
        </h2>
        {editing ? (
          <CustomRoleForm
            businessId={businessId}
            roles={roles}
            editing={editing === 'new' ? null : editing}
            onClose={(saved) => {
              setEditing(null)
              if (saved) setMsg({ text: saved })
            }}
          />
        ) : (
          <p>
            <button type="button" onClick={() => { setMsg(null); setEditing('new') }}>
              Make a role
            </button>
          </p>
        )}
        {msg ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
        {roles.custom.length === 0 && !editing ? (
          <div className="bos-empty">
            No roles of your own yet. Start from a ready-made role and keep only what this person needs.
          </div>
        ) : (
          <div className="bos-grid">
            {roles.custom.map((r) => (
              <RoleCard key={r.key} role={r} words={roles.permission_words}>
                <div className="bos-tool__foot" style={{ justifyContent: 'space-between' }}>
                  <span className="bos-hint" style={{ margin: 0 }}>
                    {r.holders ? `${r.holders} ${r.holders === 1 ? 'person has' : 'people have'} this role` : 'Nobody has this role yet'}
                  </span>
                  <span>
                    <button type="button" className="btn-quiet" onClick={() => setEditing(r)} disabled={pending}>Edit</button>
                    <button
                      type="button"
                      className="btn-quiet"
                      disabled={pending}
                      onClick={() =>
                        start(async () => {
                          const res = await removeCustomRole(businessId, r.id ?? '')
                          setMsg(res.ok ? { text: `${r.label} removed.` } : { text: res.message, bad: true })
                        })
                      }
                    >
                      Remove
                    </button>
                  </span>
                </div>
              </RoleCard>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

function CustomRoleForm({
  businessId,
  roles,
  editing,
  onClose,
}: {
  businessId: string
  roles: RoleCatalogue
  editing: RoleOption | null
  onClose: (saved: string | null) => void
}) {
  const [name, setName] = useState(editing?.label ?? '')
  const [basedOn, setBasedOn] = useState<string>(roles.templates[0]?.key ?? '')
  const [scope, setScope] = useState(editing?.scope ?? 'business')
  const [perms, setPerms] = useState<string[]>(editing?.permissions ?? roles.templates[0]?.permissions ?? [])
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const groups = useMemo(
    () => groupPermissions(Object.keys(roles.permission_words), roles.permission_words),
    [roles.permission_words],
  )

  const startFrom = (key: string) => {
    setBasedOn(key)
    const tpl = roles.templates.find((t) => t.key === key)
    if (tpl) {
      setPerms(tpl.permissions)
      setScope(tpl.scope in roles.scopes ? tpl.scope : 'business')
    }
  }

  return (
    <form
      className="bos-card bos-roleform"
      aria-label={editing ? `Edit ${editing.label}` : 'Make a role'}
      onSubmit={(e) => {
        e.preventDefault()
        setError(null)
        start(async () => {
          const r = await saveCustomRole(businessId, {
            id: editing?.id, name: name.trim(), based_on: editing ? null : basedOn || null, permissions: perms, scope,
          })
          if (r.ok) onClose(editing ? 'Role updated. People with it get the change the next time they open Workspace.' : 'Role made. Give it to someone from the Team page.')
          else setError(r.message)
        })
      }}
    >
      <div className="bos-form-grid">
        <label>
          <span className="bos-label">Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={60} placeholder="Counter helper" />
        </label>
        {!editing ? (
          <label>
            <span className="bos-label">Start from</span>
            <select value={basedOn} onChange={(e) => startFrom(e.target.value)}>
              {roles.templates.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
          </label>
        ) : null}
      </div>
      {!editing ? (
        <fieldset className="bos-choices" style={{ border: 0, padding: 0, margin: '1rem 0 0' }}>
          <legend className="bos-label">Where</legend>
          {Object.entries(roles.scopes).map(([k, words]) => (
            <label key={k} className="bos-choice">
              <input type="radio" name="scope" checked={scope === k} onChange={() => setScope(k)} />
              {words}
            </label>
          ))}
        </fieldset>
      ) : null}
      <fieldset className="bos-permpick">
        <legend className="bos-label">What they can do ({perms.length})</legend>
        {groups.map((g) => (
          <div key={g.area} className="bos-permpick__group">
            <strong>{g.label}</strong>
            {g.items.map((i) => (
              <label key={i.id} className="bos-toggle">
                <input
                  type="checkbox"
                  checked={perms.includes(i.id)}
                  onChange={() => setPerms((s) => (s.includes(i.id) ? s.filter((x) => x !== i.id) : [...s, i.id]))}
                />
                <span className="bos-toggle__track" aria-hidden />
                <span>{i.label}</span>
              </label>
            ))}
          </div>
        ))}
      </fieldset>
      {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
      <div className="bos-meter__actions">
        <button type="submit" disabled={pending || perms.length === 0}>{pending ? 'Saving…' : editing ? 'Save role' : 'Make role'}</button>
        <button type="button" className="btn-quiet" onClick={() => onClose(null)} disabled={pending}>Cancel</button>
      </div>
    </form>
  )
}
