import Link from 'next/link'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'

export const dynamic = 'force-dynamic'

type BusinessSummary = {
  id: string
  display_name: string
  slug?: string | null
  state?: string | null
  status?: string | null
}

/**
 * The Workspace front door.
 *
 * This page used to be a fixed "Sign in to continue" panel, which meant an
 * owner who was already signed in was told to sign in — the same dead end
 * whichever way they arrived. What belongs here is a decision, not a message:
 * who is this, and which business are they opening?
 *
 *   - signed out          -> the shared sign-in on the public app, with a
 *                            destination so they come back here
 *   - signed in, 1 business -> straight into it; a picker of one is friction
 *   - signed in, several    -> pick one
 *   - signed in, none       -> onboarding, which lives on the public app
 */
export default async function WorkspaceIndexPage() {
  const token = await getAccessToken()
  if (!token) {
    redirect(`${platformUrl('web', '/login')}?destination=%2Fworkspace`)
  }

  const res = await apiTry<{ data: BusinessSummary[] }>('/v1/platform/businesses', token)
  if (!res.ok) {
    // The session is good but the API is not. Saying so beats a sign-in prompt,
    // which would send the owner round a loop that cannot fix anything.
    return (
      <Shell title="Workspace is not reachable right now">
        <p style={paragraph}>
          You are signed in, but we could not load your businesses. This is on our side.
          Try again in a moment.
        </p>
        <Link href="/" style={linkStyle}>
          Try again
        </Link>
      </Shell>
    )
  }

  const businesses = res.data.data || []

  if (businesses.length === 0) {
    redirect(platformUrl('web', '/start'))
  }

  if (businesses.length === 1) {
    redirect(`/b/${businesses[0].id}`)
  }

  return (
    <Shell title="Which business?">
      <p style={paragraph}>You have more than one. Pick the one you are working on.</p>
      <ul style={{ listStyle: 'none', padding: 0, margin: '1.5rem 0 0', display: 'grid', gap: '0.6rem' }}>
        {businesses.map((b) => (
          <li key={b.id}>
            <Link href={`/b/${b.id}`} style={businessRow}>
              <span style={{ fontWeight: 600 }}>{b.display_name}</span>
              {b.state && b.state !== 'active' ? (
                <span style={statePill}>{b.state === 'draft' ? 'Not live yet' : b.state}</span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
    </Shell>
  )
}

const paragraph = { lineHeight: 1.55, margin: 0, color: '#4a4a46' } as const

const linkStyle = {
  display: 'inline-block',
  marginTop: '1.25rem',
  color: '#1b1f3b',
} as const

const businessRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '1rem',
  padding: '0.85rem 1rem',
  borderRadius: '10px',
  border: '1px solid #d8d4cc',
  background: '#ffffff',
  textDecoration: 'none',
  color: '#1b1f3b',
} as const

const statePill = {
  fontSize: '0.75rem',
  color: '#6b6862',
  border: '1px solid #d8d4cc',
  borderRadius: '999px',
  padding: '0.15rem 0.6rem',
} as const

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        fontFamily: 'Georgia, serif',
        background: 'linear-gradient(160deg, #f7f3eb 0%, #e8eef2 100%)',
        padding: '2rem',
      }}
    >
      <div style={{ maxWidth: '32rem', width: '100%' }}>
        <h1 style={{ fontSize: '1.9rem', marginBottom: '0.75rem' }}>{title}</h1>
        {children}
      </div>
    </div>
  )
}
