import Link from 'next/link'
import IndexingHealthClient from './IndexingHealthClient'

/**
 * Admin indexing health UI (Doc 11 §17.3).
 * Per-Business staleness, manual re-index, and dead-letter visibility.
 */
export default function AdminIndexingHealthPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        padding: '2rem',
        background: '#0f1419',
        color: '#e8eef4',
      }}
    >
      <p style={{ marginBottom: '0.75rem' }}>
        <Link href="/" style={{ color: '#9fd0ff' }}>
          ← Admin home
        </Link>
      </p>
      <h1 style={{ fontSize: '1.75rem' }}>Marketplace indexing health</h1>
      <p style={{ maxWidth: '42rem', lineHeight: 1.5, opacity: 0.85 }}>
        Super Admin recovery surface for projection staleness, manual re-index, and indexing
        dead-letters. Worker job <code>marketplace.reconcile</code> repairs drift periodically.
      </p>
      <IndexingHealthClient />
    </div>
  )
}
