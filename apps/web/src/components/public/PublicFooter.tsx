import Link from 'next/link'
import { Wordmark } from './Wordmark'
import { MERCHANT } from '@/lib/merchant-details'

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
      { href: '/marketplace/search', label: 'Search businesses' },
      { href: '/marketplace/categories', label: 'All categories' },
      { href: '/activity', label: 'Your orders & bookings' },
    ],
  },
  {
    title: 'Help & policies',
    links: [
      { href: '/contact', label: 'Contact us' },
      { href: '/policies', label: 'All policies' },
      { href: '/terms', label: 'Terms & Conditions' },
      { href: '/privacy', label: 'Privacy Policy' },
      { href: '/refunds', label: 'Refund & Cancellation Policy' },
      { href: '/delivery', label: 'Shipping & Digital Delivery Policy' },
      { href: '/disclaimer', label: 'Disclaimer' },
    ],
  },
]

export function PublicFooter() {
  return (
    <footer className="lc-footer">
      <div className="lc-container lc-container--wide">
        <p className="lc-footer__statement">
          Local businesses. <em>Limitless possibilities.</em>
        </p>
        <div className="ui-footer-grid">
          <div>
            <span className="lc-footer__mark"><Wordmark /></span>
            <p className="lc-muted lc-small" style={{ marginTop: '0.9rem', maxWidth: '30ch' }}>
              The digital operating layer for local businesses. Build your presence, get
              discovered, and run the whole business in one place.
            </p>
            <address className="ui-footer-address">
              Operated by {MERCHANT.legalName}<br />
              {MERCHANT.addressLine}<br />
              {MERCHANT.cityLine}, {MERCHANT.country}<br />
              <a href={`mailto:${MERCHANT.email}`}>{MERCHANT.email}</a><br />
              <a href={MERCHANT.phoneHref}>{MERCHANT.phone}</a>
            </address>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.title}>
              <p className="lc-eyebrow">{col.title}</p>
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
            &copy; {new Date().getFullYear()} LOCAH. Operated by {MERCHANT.legalName}.
          </span>
        </div>
      </div>
    </footer>
  )
}
