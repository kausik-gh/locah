import Link from 'next/link'

const LINKS = [
  {
    href: '/businesses',
    title: 'Businesses',
    body: 'Search every joined Business; open one for the support view — modules, locations, standing.',
  },
  {
    href: '/audit',
    title: 'Audit & Activity',
    body: 'Append-only evidence view over platform audit events. Filter by business, actor, event type.',
  },
  {
    href: '/system',
    title: 'System Health',
    body: 'Dead letters, outbox backlog, failed jobs, and the event types that are failing.',
  },
  {
    href: '/marketplace/indexing',
    title: 'Marketplace Indexing',
    body: 'Projection staleness, manual re-index, and indexing dead letters.',
  },
]

export default function AdminHomePage() {
  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>LOCAH Super Admin</h1>
      <p style={{ opacity: 0.8, maxWidth: '46rem', lineHeight: 1.6 }}>
        Support and observation, never silent impersonation. Every inspection of an identified
        Business is written to the audit trail as an <code>admin.*</code> event attributed to your
        own identity.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(18rem, 1fr))',
          gap: '0.9rem',
          marginTop: '1.75rem',
        }}
      >
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            style={{
              display: 'block',
              padding: '1.1rem 1.2rem',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'rgba(255,255,255,0.03)',
              color: '#e8eef4',
              textDecoration: 'none',
            }}
          >
            <strong style={{ fontSize: '1.05rem' }}>{link.title}</strong>
            <p style={{ opacity: 0.75, margin: '0.4rem 0 0', fontSize: '0.9rem', lineHeight: 1.5 }}>
              {link.body}
            </p>
          </Link>
        ))}
      </div>
    </div>
  )
}
