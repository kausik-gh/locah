'use client'

import { useFormState, useFormStatus } from 'react-dom'
import { claimModulesAction, type ClaimState } from './actions'

export type Recommendation = {
  module_id: string
  rationale: string
  rank: number
  display_name: string
  already_active: boolean
}
export type CatalogEntry = { module_id: string; display_name: string }

const INITIAL: ClaimState = { error: null }

function Submit({ count }: { count: number }) {
  const { pending } = useFormStatus()
  return (
    <button
      type="submit"
      disabled={pending}
      style={{
        padding: '0.75rem 1.5rem',
        borderRadius: '8px',
        border: 'none',
        background: pending ? '#7d9c96' : '#1c5f57',
        color: '#fff',
        fontWeight: 600,
        fontSize: '0.98rem',
        cursor: pending ? 'progress' : 'pointer',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      {pending
        ? 'Turning them on…'
        : count > 0
          ? 'Turn these on & open my Workspace →'
          : 'Open my Workspace →'}
    </button>
  )
}

function Row({
  moduleId,
  title,
  detail,
  defaultChecked,
  disabled,
}: {
  moduleId: string
  title: string
  detail: string
  defaultChecked: boolean
  disabled?: boolean
}) {
  return (
    <label
      style={{
        display: 'flex',
        gap: '0.85rem',
        alignItems: 'flex-start',
        padding: '0.95rem 1.1rem',
        borderRadius: '10px',
        border: '1px solid rgba(28,36,48,0.14)',
        background: disabled ? 'rgba(28,95,87,0.07)' : 'rgba(255,255,255,0.7)',
        cursor: disabled ? 'default' : 'pointer',
      }}
    >
      <input
        type="checkbox"
        name="modules"
        value={moduleId}
        defaultChecked={defaultChecked}
        disabled={disabled}
        style={{ marginTop: '0.25rem', width: '1.05rem', height: '1.05rem' }}
      />
      <span style={{ display: 'grid', gap: '0.2rem' }}>
        <span style={{ fontWeight: 600 }}>
          {title}
          {disabled ? (
            <span
              style={{
                marginLeft: '0.5rem',
                fontSize: '0.72rem',
                fontWeight: 600,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                color: '#1c5f57',
              }}
            >
              Already on
            </span>
          ) : null}
        </span>
        <span
          style={{
            fontFamily: 'system-ui, sans-serif',
            fontSize: '0.88rem',
            color: '#4c5967',
            lineHeight: 1.5,
          }}
        >
          {detail}
        </span>
      </span>
    </label>
  )
}

export function ClaimForm({
  businessId,
  recommendations,
  others,
}: {
  businessId: string
  recommendations: Recommendation[]
  others: CatalogEntry[]
}) {
  const [state, formAction] = useFormState(claimModulesAction, INITIAL)
  const claimable = recommendations.filter((r) => !r.already_active)

  return (
    <form action={formAction} style={{ display: 'grid', gap: '1.5rem' }}>
      <input type="hidden" name="business_id" value={businessId} />

      {state.error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            padding: '0.8rem 1rem',
            borderRadius: '8px',
            border: '1px solid #c9776f',
            background: '#f8e9e7',
            color: '#8d2f24',
            fontFamily: 'system-ui, sans-serif',
            fontSize: '0.92rem',
            lineHeight: 1.6,
          }}
        >
          {state.error}
        </p>
      ) : null}

      <div style={{ display: 'grid', gap: '0.7rem' }}>
        {recommendations.map((r) => (
          <Row
            key={r.module_id}
            moduleId={r.module_id}
            title={r.display_name}
            detail={r.rationale}
            defaultChecked={!r.already_active}
            disabled={r.already_active}
          />
        ))}
      </div>

      {others.length > 0 ? (
        <details style={{ fontFamily: 'system-ui, sans-serif' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: '0.95rem' }}>
            Everything else available ({others.length})
          </summary>
          <div style={{ display: 'grid', gap: '0.7rem', marginTop: '0.9rem' }}>
            {others.map((m) => (
              <Row
                key={m.module_id}
                moduleId={m.module_id}
                title={m.display_name}
                detail="Not typical for your kind of business — turn it on if you need it."
                defaultChecked={false}
              />
            ))}
          </div>
        </details>
      ) : null}

      <Submit count={claimable.length} />
    </form>
  )
}
