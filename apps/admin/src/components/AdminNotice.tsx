import Link from 'next/link'
import { ReactNode } from 'react'
import type { ApiError } from '@/lib/api'

/**
 * Admin-side equivalent of the Workspace `GateNotice` — renders the actual
 * reason an Admin page could not load, never a blank screen (Doc 11 §17.7).
 *
 * The Admin failure modes are narrower than a Business page's: there is no
 * module or entitlement gate here, only authentication and the Super Admin
 * check.
 */

const CARD: React.CSSProperties = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.14)',
  borderRadius: '10px',
  padding: '1.5rem',
  maxWidth: '44rem',
}

export function AdminNotice({
  error,
  context,
}: {
  error: ApiError | { status: 0; code: 'NO_SESSION'; message: string }
  context?: string
}) {
  if (error.code === 'NO_SESSION' || error.status === 401) {
    return (
      <div style={CARD}>
        <h2 style={{ marginTop: 0 }}>You are not signed in</h2>
        <p style={{ opacity: 0.85 }}>
          Super Admin pages require an authenticated session. Sign in with an account that holds a
          platform admin grant, then reload.
        </p>
      </div>
    )
  }
  if (error.status === 403) {
    return (
      <div style={CARD}>
        <h2 style={{ marginTop: 0 }}>This account is not a Super Admin</h2>
        <p style={{ opacity: 0.85 }}>
          You are signed in, but your identity does not hold an active{' '}
          <code>platform_admin_grants</code> row. Ask an existing Super Admin to grant access, with
          a reason on record.
        </p>
      </div>
    )
  }
  if (error.status === 404) {
    return (
      <div style={CARD}>
        <h2 style={{ marginTop: 0 }}>Not found</h2>
        <p style={{ opacity: 0.85 }}>{context ?? 'That record does not exist.'}</p>
        <Link href="/businesses" style={{ color: '#9fd0ff' }}>
          ← Back to Businesses
        </Link>
      </div>
    )
  }
  return (
    <div style={CARD}>
      <h2 style={{ marginTop: 0 }}>Could not load this page</h2>
      <p style={{ opacity: 0.85 }}>{error.message}</p>
      <p style={{ opacity: 0.55, fontSize: '0.85rem' }}>Reference: {error.code}</p>
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        gap: '1rem',
        flexWrap: 'wrap',
        marginBottom: '1.25rem',
      }}
    >
      <div>
        <h1 style={{ fontSize: '1.9rem', margin: 0 }}>{title}</h1>
        {subtitle ? <p style={{ opacity: 0.75, margin: '0.35rem 0 0' }}>{subtitle}</p> : null}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p
      style={{
        marginTop: '1rem',
        padding: '1.1rem 1.25rem',
        background: 'rgba(255,255,255,0.03)',
        border: '1px dashed rgba(255,255,255,0.2)',
        borderRadius: '8px',
        opacity: 0.8,
      }}
    >
      {children}
    </p>
  )
}

export const TABLE: React.CSSProperties = { width: '100%', borderCollapse: 'collapse' }
export const TH: React.CSSProperties = {
  padding: '0.45rem 0.5rem',
  textAlign: 'left',
  opacity: 0.65,
  fontWeight: 600,
  fontSize: '0.8rem',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
}
export const TD: React.CSSProperties = { padding: '0.55rem 0.5rem', verticalAlign: 'top' }
export const ROW: React.CSSProperties = { borderTop: '1px solid rgba(255,255,255,0.1)' }
export const MONO: React.CSSProperties = {
  fontFamily: 'ui-monospace, "SF Mono", monospace',
  fontSize: '0.82rem',
}

export function Pill({ value }: { value: string }) {
  const tone: Record<string, string> = {
    active: '#5fd39a',
    in_good_standing: '#5fd39a',
    ready: '#5fd39a',
    completed: '#5fd39a',
    onboarding: '#e0b654',
    draft: '#8a94a3',
    pending: '#e0b654',
    under_review: '#e0b654',
    suspended: '#f08a80',
    failed: '#f08a80',
    dead_letter: '#f08a80',
    closed: '#8a94a3',
    dormant: '#8a94a3',
  }
  const color = tone[value] ?? '#c7d0da'
  return (
    <span
      style={{
        color,
        border: `1px solid ${color}40`,
        background: `${color}1a`,
        borderRadius: '999px',
        padding: '0.1rem 0.55rem',
        fontSize: '0.82rem',
        whiteSpace: 'nowrap',
      }}
    >
      {value}
    </span>
  )
}
