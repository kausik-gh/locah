import Link from 'next/link'
import { Wordmark } from './Wordmark'

/**
 * The chrome on every LOCAH-owned public page (marketing, Marketplace, search).
 * Deliberately NOT used on a published tenant website — those get their own
 * business's header, because the visitor is there for the business, not for us.
 */

export type PublicNavProps = {
  /** Highlights the current destination. */
  active?: 'marketplace' | 'business' | 'capabilities'
  /** Signed-in visitors get "Your workspace" instead of "Get started". */
  signedIn?: boolean
  /** Consumer surfaces must not offer "Your businesses" — a customer who never
   *  runs a business should not be pointed at the operator side of LOCAH. */
  audience?: 'business' | 'consumer'
}

const LINKS: Array<{ href: string; label: string; key: PublicNavProps['active'] }> = [
  { href: '/marketplace', label: 'Marketplace', key: 'marketplace' },
  { href: '/for-businesses', label: 'For businesses', key: 'business' },
  { href: '/capabilities', label: 'Capabilities', key: 'capabilities' },
]

export function PublicNav({
  active,
  signedIn = false,
  audience = 'business',
}: PublicNavProps) {
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
            <Link
              className="lc-btn lc-btn--primary lc-btn--sm"
              href={audience === 'consumer' ? '/activity' : '/'}
            >
              {audience === 'consumer' ? 'Your activity' : 'Your businesses'}
            </Link>
          ) : (
            <>
              <Link className="lc-nav__link lc-hide-sm" href="/login">
                Sign in
              </Link>
              <Link className="lc-btn lc-btn--primary lc-btn--sm" href="/start">
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
