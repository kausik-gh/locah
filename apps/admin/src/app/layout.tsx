import React from 'react'
import Link from 'next/link'

export const metadata = {
  title: 'LOCAH Admin',
  description: 'LOCAH Super Admin dashboard',
}

const NAV = [
  { href: '/businesses', label: 'Businesses' },
  { href: '/audit', label: 'Audit & Activity' },
  { href: '/system', label: 'System Health' },
  { href: '/marketplace/indexing', label: 'Indexing' },
]

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: 'ui-sans-serif, system-ui, -apple-system, sans-serif',
          background: '#0f1419',
          color: '#e8eef4',
          minHeight: '100vh',
        }}
      >
        <div style={{ display: 'grid', gridTemplateColumns: '210px 1fr', minHeight: '100vh' }}>
          <aside
            style={{
              padding: '1.4rem 1rem',
              borderRight: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            <Link
              href="/"
              style={{ color: '#e8eef4', textDecoration: 'none', fontWeight: 700, letterSpacing: '0.02em' }}
            >
              Super Admin
            </Link>
            <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '1.1rem' }}>
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  style={{
                    color: '#c7d0da',
                    textDecoration: 'none',
                    padding: '0.4rem 0.55rem',
                    borderRadius: '6px',
                    fontSize: '0.92rem',
                  }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main style={{ padding: '2rem' }}>{children}</main>
        </div>
      </body>
    </html>
  )
}
