import Link from 'next/link'
import { CommerceCart } from './CommerceCart'
import { SectionRenderer, type SiteContact } from './SectionRenderer'
import { siteFontVariables } from './site-fonts'
import { withPreviewToken } from './preview-links'
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

function finite(value: unknown, allowed: readonly string[], fallback: string) {
  const candidate = String(value || '')
  return allowed.includes(candidate) ? candidate : fallback
}

type StrategyDecision = { section_type_id: string; emphasis: string; include?: boolean }

/** Read the persisted design strategy defensively — it is data, not a contract. */
function strategyDecisions(theme: Record<string, unknown>): StrategyDecision[] {
  const strategy = theme.design_strategy
  if (!strategy || typeof strategy !== 'object') return []
  const variants = (strategy as Record<string, unknown>).section_variants
  if (!Array.isArray(variants)) return []
  return variants.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const id = typeof row.section_type_id === 'string' ? row.section_type_id : ''
    const emphasis = typeof row.emphasis === 'string' ? row.emphasis : 'supporting'
    if (!id || !['primary', 'supporting', 'quiet'].includes(emphasis)) return []
    return [{ section_type_id: id, emphasis, include: row.include !== false }]
  })
}

export function WebsitePageView({
  data,
  previewToken,
}: {
  data: PublicWebsitePayload
  previewToken?: string
}) {
  const theme = data.theme || {}
  const slug = data.business.slug
  const name = data.business.display_name
  const type = (data.business.business_type || '').toLowerCase()
  const personality = String(theme.personality || '') || PERSONALITY[type] || 'clean'
  const typography = finite(
    theme.typography_direction,
    ['editorial_serif', 'modern_sans'],
    personality === 'warm' || personality === 'premium' || personality === 'dark'
      ? 'editorial_serif'
      : 'modern_sans'
  )
  const density = finite(theme.content_density, ['compact', 'balanced', 'spacious'], 'balanced')
  const heroDensity = finite(theme.hero_density, ['compact', 'balanced', 'immersive'], 'balanced')
  const motion = finite(theme.motion_preference, ['none', 'subtle'], 'subtle')
  const mobilePriority = finite(
    theme.mobile_priority,
    ['content', 'conversion', 'imagery'],
    'content'
  )
  const navigationStyle = finite(theme.navigation_style, ['standard', 'compact'], 'standard')

  const primary = String(theme.primary_color || DEFAULT_PRIMARY[personality] || '#1f3d34')
  const accent = String(theme.accent_color || primary)
  const logo = theme.logo_url ? String(theme.logo_url) : null

  const styleVars: ThemeVars = {
    '--site-primary': primary,
    '--site-primary-fg': readable(primary),
    '--site-accent': accent,
    '--site-accent-fg': readable(accent),
  }
  if (theme.text_color) styleVars['--site-ink'] = String(theme.text_color)
  if (theme.background_color) styleVars['--site-bg'] = String(theme.background_color)
  if (theme.surface_alt_color) styleVars['--site-bg-alt'] = String(theme.surface_alt_color)
  if (theme.muted_color) styleVars['--site-muted'] = String(theme.muted_color)
  const paletteMode = finite(
    theme.palette_mode,
    ['light', 'dark'],
    personality === 'dark' ? 'dark' : 'light'
  )
  if (theme.palette_mode) {
    styleVars['--site-border'] =
      paletteMode === 'dark' ? 'rgba(255, 255, 255, 0.12)' : 'rgba(16, 20, 24, 0.10)'
  }
  // The creative direction: which design language this site speaks. Finite,
  // renderer-backed values only — anything else falls back to the older look.
  const profile = finite(
    theme.reference_profile,
    [
      'bold_food_commerce',
      'editorial_home_food',
      'cinematic_fitness',
      'airy_real_estate',
      'calm_care',
      'technical_b2b',
      'friendly_local',
    ],
    ''
  )
  const typeSystem = finite(
    theme.type_system,
    [
      'bold_commerce',
      'editorial_food',
      'cinematic_fitness',
      'premium_property',
      'calm_care',
      'technical_b2b',
      'friendly_local',
    ],
    ''
  )
  const cards = finite(theme.card_style, ['sharp', 'soft', 'editorial', 'glass'], '')
  const navStyle = finite(
    theme.nav_style,
    ['commerce', 'editorial', 'cinematic', 'airy', 'standard'],
    'standard'
  )
  const motionIntensity = finite(theme.motion_intensity, ['subtle', 'lively'], 'subtle')
  const navCta =
    theme.nav_cta && typeof theme.nav_cta === 'object'
      ? (theme.nav_cta as { label?: unknown; href?: unknown })
      : null
  const utility = Array.isArray(theme.utility_bar) ? theme.utility_bar.map(String).slice(0, 2) : []

  // The tab title is set by each route's generateMetadata, not here — a <title>
  // rendered in the tree lands in <body> on React 18 and duplicates the tag.
  const contact: SiteContact = data.business.contact || {}
  const reachable = Boolean(contact.phone || contact.whatsapp)
  const nav = data.navigation || []
  const sections = data.page.sections.filter((s) => s.is_visible !== false)
  const capabilities = data.capabilities || {}
  const canOrder = Boolean(capabilities.order)
  const canBook = Boolean(capabilities.book)
  const visitLinks = [
    canOrder ? { label: 'Basket', href: `/${slug}/checkout` } : null,
    canBook ? { label: 'Book', href: `/${slug}/book` } : null,
    canOrder || canBook ? { label: 'Your orders & bookings', href: '/activity' } : null,
  ].filter((item): item is { label: string; href: string } => item !== null)

  // How loudly each section should speak. The design strategy decides this per
  // section type and it was previously computed, stored and then ignored — so a
  // menu-led restaurant and a story-led one differed only in section order.
  // Reading it here costs no schema change: the strategy already travels in the
  // theme the browser receives.
  const emphasisByType = new Map<string, string>()
  for (const decision of strategyDecisions(theme)) {
    if (decision.include !== false) emphasisByType.set(decision.section_type_id, decision.emphasis)
  }
  function emphasisFor(sectionTypeId: string): string {
    return emphasisByType.get(sectionTypeId) || 'supporting'
  }

  function navHref(path: string) {
    if (!path || path === '/') return `/${slug}`
    // "/#shop": a section of the home page. On the home page itself the plain
    // anchor keeps the visitor where they are and just scrolls.
    if (path.startsWith('/#'))
      return data.page.slug === 'home' ? path.slice(1) : `/${slug}${path.slice(1)}`
    return `/${slug}${path.startsWith('/') ? path : `/${path}`}`
  }
  const ctaLabel = navCta ? String(navCta.label || '') : ''
  const ctaHref = navCta ? String(navCta.href || '') : ''
  const ctaTarget = ctaHref.startsWith('#')
    ? data.page.slug === 'home'
      ? ctaHref
      : `/${slug}${ctaHref}`
    : ctaHref
  const callLabel =
    profile === 'bold_food_commerce' || profile === 'editorial_home_food' ? 'Call to order' : 'Call'

  return (
    <div
      className={siteFontVariables}
      data-locah-site=""
      data-personality={personality}
      data-typography={typography}
      data-density={density}
      data-hero-density={heroDensity}
      data-motion={motion}
      data-mobile-priority={mobilePriority}
      data-navigation={navigationStyle}
      data-profile={profile || undefined}
      data-type={typeSystem || undefined}
      data-palette={paletteMode}
      data-cards={cards || undefined}
      data-nav={navStyle}
      data-motion-intensity={motionIntensity}
      style={styleVars}
    >
      {data.is_preview ? (
        <aside
          aria-label="Preview status"
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
        </aside>
      ) : null}

      {utility.length && navStyle === 'commerce' ? (
        <div className="ls-utility" role="note">
          <div className="ls-utility__inner">
            {utility.map((line) => (
              <span key={line}>{line}</span>
            ))}
          </div>
        </div>
      ) : null}
      <header className={`ls-nav ls-nav--${navStyle}`}>
        <div className="ls-nav__inner">
          <Link className="ls-nav__brand" href={withPreviewToken(`/${slug}`, previewToken)}>
            {logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="ls-nav__logo" src={logo} alt="" />
            ) : null}
            <span className="ls-nav__name">{name}</span>
          </Link>
          <nav className="ls-nav__links">
            {nav.map((item) => {
              // A published tenant site must not be brought down by one
              // malformed navigation row. Skipping the link loses a menu item;
              // trusting the field lost the whole page.
              const path = typeof item.path === 'string' ? item.path : ''
              if (!path) return null
              return (
                <Link
                  key={`${item.label}-${path}`}
                  className="ls-nav__link"
                  href={withPreviewToken(navHref(path), previewToken)}
                  aria-current={
                    (path === '/' && data.page.slug === 'home') ||
                    path.replace(/^\//, '') === data.page.slug
                      ? 'page'
                      : undefined
                  }
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
          <div className="ls-nav__actions">
            {canOrder ? <CommerceCart slug={slug} /> : null}
            {ctaLabel && ctaTarget ? (
              <a
                className="ls-btn ls-btn--sm ls-nav__cta"
                href={ctaTarget}
                target={ctaTarget.startsWith('http') ? '_blank' : undefined}
                rel={ctaTarget.startsWith('http') ? 'noopener noreferrer' : undefined}
              >
                {ctaLabel}
              </a>
            ) : null}
          </div>
        </div>
      </header>

      <main>
        {sections.map((section, i) => (
          // `display: contents` so the wrapper carries the strategy's emphasis
          // for CSS without entering layout. The section element underneath is
          // still the direct child of <main> that website.css expects.
          <div
            key={section.id}
            style={{ display: 'contents' }}
            data-emphasis={emphasisFor(section.section_type_id)}
          >
            <SectionRenderer
              section={section}
              businessSlug={slug}
              index={i}
              capabilities={data.capabilities}
              contact={contact}
              businessName={name}
              previewToken={previewToken}
            />
          </div>
        ))}
      </main>

      {contact.whatsapp ? (
        <a
          className="ls-wa-float"
          href={`https://wa.me/${contact.whatsapp.replace(/\D/g, '')}`}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`WhatsApp ${name}`}
        >
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
            <path
              fill="currentColor"
              d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.4-.2Z"
            />
          </svg>
        </a>
      ) : null}

      {reachable ? (
        // On a phone the two things a visitor most wants are always one tap away.
        <nav className="ls-mobile-bar" aria-label="Contact">
          {contact.phone ? <a href={`tel:${contact.phone}`}>{callLabel}</a> : null}
          {contact.whatsapp ? (
            <a
              href={`https://wa.me/${contact.whatsapp.replace(/\D/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              WhatsApp
            </a>
          ) : null}
        </nav>
      ) : null}

      <footer className={`ls-foot ${reachable ? 'ls-foot--with-bar' : ''}`}>
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
              <p className="ls-foot__heading">Explore</p>
              {nav.map((item) => (
                <Link
                  key={`f-${item.label}`}
                  href={withPreviewToken(navHref(item.path), previewToken)}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          ) : null}
          {visitLinks.length > 0 ? (
            <div className="ls-foot__col">
              <p className="ls-foot__heading">Your visit</p>
              {visitLinks.map((item) => (
                <Link key={item.href} href={item.href}>
                  {item.label}
                </Link>
              ))}
            </div>
          ) : null}
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
