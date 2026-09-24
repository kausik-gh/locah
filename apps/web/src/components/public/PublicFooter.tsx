import Link from 'next/link'
import { Wordmark } from './Wordmark'

const COLUMNS: Array<{ title: string; links: Array<{ href: string; label: string }> }> = [
  {
    title: 'For businesses',
    links: [
      { href: '/start', label: 'Set up your business' },
      { href: '/product', label: 'The product' },
      { href: '/how-it-works', label: 'How LOCAH works' },
      { href: '/pricing', label: 'Pricing' },
      { href: '/capabilities', label: 'Capabilities' },
      { href: '/login', label: 'Sign in' },
    ],
  },
  {
    title: 'For customers',
    links: [
      { href: '/marketplace', label: 'Browse the Marketplace' },
      { href: '/search', label: 'Search businesses' },
      { href: '/activity', label: 'Your orders & bookings' },
    ],
  },
]

export function PublicFooter() {
  return (
    <footer className="lc-footer">
      <div className="lc-container lc-container--wide">
        <div className="lc-grid lc-grid--3">
          <div>
            <Wordmark />
            <p className="lc-muted lc-small" style={{ marginTop: '0.9rem', maxWidth: '30ch' }}>
              The digital operating layer for local businesses. Build your presence, get
              discovered, and run the whole business in one place.
            </p>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h4 className="lc-eyebrow">{col.title}</h4>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.55rem' }}>
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link className="lc-link" href={l.href}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="lc-footer__bottom">
          <span className="lc-small lc-muted">
            &copy; {new Date().getFullYear()} LOCAH — Local Businesses. Limitless Possibilities.
          </span>
        </div>
      </div>
    </footer>
  )
}
