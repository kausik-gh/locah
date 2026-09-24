import Link from 'next/link'
import { platformUrl } from '@platform/config'
import { Wordmark } from './Wordmark'

/**
 * The chrome on every LOCAH-owned public page (marketing, Marketplace, search).
 * Deliberately NOT used on a published tenant website — those get their own
 * business's header, because the visitor is there for the business, not for us.
 */

export type NavBusiness = { id: string; display_name: string; business_type?: string | null }

export type PublicNavProps = {
  /** Highlights the current destination. */
  active?: 'marketplace' | 'business' | 'capabilities' | 'product' | 'how' | 'pricing' | 'contact'
  /** Signed-in visitors get the account menu instead of "Sign in". */
  signedIn?: boolean
  /** The businesses this person runs, for the switcher. Empty for a customer. */
  businesses?: NavBusiness[]
  /** Consumer surfaces must not offer "Your businesses" — a customer who never
   *  runs a business should not be pointed at the operator side of LOCAH. */
  audience?: 'business' | 'consumer'
}

const LINKS: Array<{ href: string; label: string; key: PublicNavProps['active'] }> = [
  { href: '/marketplace', label: 'Marketplace', key: 'marketplace' },
  { href: '/product', label: 'Product', key: 'product' },
  { href: '/how-it-works', label: 'How it works', key: 'how' },
  { href: '/pricing', label: 'Pricing', key: 'pricing' },
]

const WORKSPACE_URL = platformUrl('workspace')

function Caret() {
  return (
    <svg className="lc-acct__caret" viewBox="0 0 10 10" aria-hidden="true" fill="none">
      <path d="M1.5 3.5 5 7l3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function AccountMenu({ businesses, audience }: { businesses: NavBusiness[]; audience: 'business' | 'consumer' }) {
  const first = businesses[0]
  const label = audience === 'business' && first ? first.display_name : 'Your account'
  const initial = (first?.display_name || 'You').trim().slice(0, 1).toUpperCase()
  return (
    <details className="lc-acct">
      <summary aria-label={`Account menu, ${label}`}>
        <span className="lc-acct__avatar" aria-hidden="true">{initial}</span>
        <span className="lc-acct__name">{label}</span>
        <Caret />
      </summary>
      <div className="lc-acct__panel">
        {audience === 'business' && businesses.length > 0 ? (
          <>
            <p className="lc-acct__label">Your businesses</p>
            {businesses.slice(0, 6).map((b) => (
              <a className="lc-acct__biz" key={b.id} href={`${WORKSPACE_URL}/b/${b.id}`}>
                <span className="lc-acct__biz-mark" aria-hidden="true">
                  {b.display_name.trim().slice(0, 1).toUpperCase()}
                </span>
                <span>
                  <strong>{b.display_name}</strong>
                  <small>Workspace</small>
                </span>
                <span className="lc-acct__go">Open</span>
              </a>
            ))}
          </>
        ) : null}
        <div className="lc-acct__links">
          {audience === 'business' ? <Link href="/start">Start another business</Link> : null}
          <Link href="/activity">Your orders and bookings</Link>
          <form action="/auth/logout" method="post">
            <button type="submit">Sign out</button>
          </form>
        </div>
      </div>
    </details>
  )
}

export function PublicNav({
  active,
  signedIn = false,
  businesses = [],
  audience = 'business',
}: PublicNavProps) {
  const first = audience === 'business' ? businesses[0] : undefined
  return (
    <header className="lc-nav">
      <div className="lc-nav__inner lc-container lc-container--wide">
        <Link className="lc-nav__brand" href="/" aria-label="LOCAH home">
          <Wordmark />
        </Link>

        {/* No lc-hide-sm here: .lc-nav__links owns its own breakpoint, and the
            utility's `display: revert` would cancel the flex layout. */}
        <nav className="lc-nav__links" aria-label="Main">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              className="lc-nav__link"
              href={l.href}
              aria-current={active === l.key ? 'page' : undefined}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="lc-nav__actions">
          {signedIn ? (
            <>
              {first ? (
                <a className="lc-btn lc-btn--ink lc-btn--sm lc-hide-sm" href={`${WORKSPACE_URL}/b/${first.id}`}>
                  Open Workspace
                </a>
              ) : null}
              <AccountMenu businesses={businesses} audience={audience} />
            </>
          ) : (
            <>
              <Link className="lc-nav__signin lc-hide-sm" href="/login">
                Sign in
              </Link>
              <Link className="lc-btn lc-btn--primary lc-btn--sm" href="/start">
                Start your business
              </Link>
            </>
          )}
        </div>
        <details className="lc-mobile-menu">
          <summary aria-label="Menu">Menu</summary>
          <nav aria-label="Mobile main">
            {LINKS.map((l) => (
              <Link key={l.href} href={l.href} aria-current={active === l.key ? 'page' : undefined}>
                {l.label}
              </Link>
            ))}
            <Link href="/for-businesses">For businesses</Link>
            <Link href="/contact">Contact</Link>
            <span className="lc-mobile-menu__sep" aria-hidden="true" />
            {signedIn ? (
              <>
                {first ? (
                  <a className="lc-btn lc-btn--ink" href={`${WORKSPACE_URL}/b/${first.id}`}>
                    Open Workspace
                  </a>
                ) : null}
                <Link href="/activity">Your orders and bookings</Link>
              </>
            ) : (
              <>
                <Link href="/login">Sign in</Link>
                <Link className="lc-btn lc-btn--primary" href="/start">
                  Start your business
                </Link>
              </>
            )}
          </nav>
        </details>
      </div>
    </header>
  )
}
