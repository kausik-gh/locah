import Link from 'next/link'
import { SectionRenderer } from './SectionRenderer'
import type { PublicWebsitePayload } from '@/lib/public-website'

/**
 * The shell of a published tenant website.
 *
 * Its job is to translate the business's stored `theme` record into the
 * `--site-*` contract that website.css reads, so the page looks like THAT
 * business rather than like LOCAH. Business type also selects a "personality"
 * preset, which changes proportion, corner treatment and display font — the
 * reason two businesses on the same platform do not look like the same site
 * in a different colour.
 */

type ThemeVars = React.CSSProperties & Record<`--${string}`, string | undefined>

/** Doc 12 §11.4 business types → visual personality. */
const PERSONALITY: Record<string, string> = {
  restaurant: 'warm',
  cafe: 'warm',
  home_food: 'warm',
  bakery: 'warm',
  hotel: 'premium',
  homestay: 'premium',
  spa: 'premium',
  salon: 'premium',
  gym: 'bold',
  studio: 'bold',
  fitness: 'bold',
  clinic: 'premium',
  retail: 'clean',
  professional_service: 'clean',
  education: 'clean',
  real_estate: 'clean',
}

/** Neutral, non-LOCAH defaults per personality when a theme omits colours. */
const DEFAULT_PRIMARY: Record<string, string> = {
  warm: '#8a3a1e',
  premium: '#1f3d34',
  bold: '#15161a',
  clean: '#17457a',
  dark: '#e6e2da',
}

function readable(hex: string): string {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim())
  if (!m) return '#ffffff'
  const [r, g, b] = [m[1], m[2], m[3]].map((h) => parseInt(h, 16))
  // Relative luminance — pick the foreground that actually passes on this hue.
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
  return lum > 0.6 ? '#111111' : '#ffffff'
}

export function WebsitePageView({ data }: { data: PublicWebsitePayload }) {
  const theme = data.theme || {}
  const slug = data.business.slug
  const name = data.business.display_name
  const type = (data.business.business_type || '').toLowerCase()
  const personality =
    String(theme.personality || '') || PERSONALITY[type] || 'clean'

  const primary = String(theme.primary_color || DEFAULT_PRIMARY[personality] || '#1f3d34')
  const accent = String(theme.accent_color || primary)
  const logo = theme.logo_url ? String(theme.logo_url) : null

  const styleVars: ThemeVars = {
    '--site-primary': primary,
    '--site-primary-fg': readable(primary),
    '--site-accent': accent,
  }
  if (theme.text_color) styleVars['--site-ink'] = String(theme.text_color)
  if (theme.background_color) styleVars['--site-bg'] = String(theme.background_color)

  // The tab title is set by each route's generateMetadata, not here — a <title>
  // rendered in the tree lands in <body> on React 18 and duplicates the tag.
  const nav = data.navigation || []
  const sections = data.page.sections.filter((s) => s.is_visible !== false)

  function navHref(path: string) {
    if (!path || path === '/') return `/${slug}`
    return `/${slug}${path.startsWith('/') ? path : `/${path}`}`
  }

  return (
    <div data-locah-site="" data-personality={personality} style={styleVars}>
      {data.is_preview ? (
        <div
          style={{
            background: '#111827',
            color: '#fff',
            padding: '0.6rem 1rem',
            fontSize: '0.82rem',
            textAlign: 'center',
            letterSpacing: '0.02em',
          }}
        >
          Preview — this is a draft. Visitors still see your published site.
        </div>
      ) : null}

      <header className="ls-nav">
        <div className="ls-nav__inner">
          <Link className="ls-nav__brand" href={`/${slug}`}>
            {logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="ls-nav__logo" src={logo} alt="" />
            ) : null}
            {name}
          </Link>
          <nav className="ls-nav__links">
            {nav.map((item) => (
              <Link
                key={`${item.label}-${item.path}`}
                className="ls-nav__link"
                href={navHref(item.path)}
                aria-current={
                  (item.path === '/' && data.page.slug === 'home') ||
                  item.path.replace(/^\//, '') === data.page.slug
                    ? 'page'
                    : undefined
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {sections.map((section, i) => (
          <SectionRenderer
            key={section.id}
            section={section}
            businessSlug={slug}
            index={i}
            capabilities={data.capabilities}
          />
        ))}
      </main>

      <footer className="ls-foot">
        <div className="ls-foot__inner">
          <div>
            <p className="ls-foot__name">{name}</p>
            {theme.tagline ? (
              <p style={{ color: 'var(--site-muted)', fontSize: '0.92rem', maxWidth: '38ch' }}>
                {String(theme.tagline)}
              </p>
            ) : null}
          </div>
          {nav.length > 0 ? (
            <div className="ls-foot__col">
              <h4>Explore</h4>
              {nav.map((item) => (
                <Link key={`f-${item.label}`} href={navHref(item.path)}>
                  {item.label}
                </Link>
              ))}
            </div>
          ) : null}
          <div className="ls-foot__col">
            <h4>Your visit</h4>
            <Link href={`/${slug}/checkout`}>Basket</Link>
            <Link href="/activity">Your orders &amp; bookings</Link>
          </div>
        </div>
        <div className="ls-foot__bar">
          <span>
            &copy; {new Date().getFullYear()} {name}
          </span>
          <Link className="ls-foot__by" href="/">
            Powered by LOCAH
          </Link>
        </div>
      </footer>
    </div>
  )
}
