import Link from 'next/link'

export default function WorkspaceIndexPage() {
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
      <div style={{ maxWidth: '32rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>LOCAH Workspace</h1>
        <p style={{ lineHeight: 1.5, marginBottom: '1.25rem' }}>
          Sign in to open your business — your website, offerings, orders, customers, and
          settings all live here.
        </p>
        <Link href="/login">Sign in to continue</Link>
      </div>
    </div>
  )
}
