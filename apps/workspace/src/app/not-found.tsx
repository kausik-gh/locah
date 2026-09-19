import Link from 'next/link'

/**
 * What a person sees when a Workspace address does not resolve for them.
 *
 * It covers two cases on purpose and does not distinguish them: an address that
 * does not exist, and a business they are not a member of. Saying which would
 * turn this page into a way to test whether a given business id is real.
 */
export default function WorkspaceNotFound() {
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
      <div style={{ maxWidth: '30rem' }}>
        <h1 style={{ fontSize: '1.9rem', margin: '0 0 0.7rem' }}>Not your business</h1>
        <p style={{ lineHeight: 1.6, color: '#4a4a46', margin: 0 }}>
          This page either does not exist, or belongs to a business you are not part of. If a
          colleague sent you here, ask them to invite you to the business first.
        </p>
        <p style={{ marginTop: '1.5rem' }}>
          <Link href="/" style={{ color: '#1b1f3b' }}>
            Go to your Workspace
          </Link>
        </p>
      </div>
    </div>
  )
}
