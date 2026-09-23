import Link from 'next/link'
import { LiveItemsSection } from './LiveItemsSection'
import { withPreviewToken } from './preview-links'

/**
 * Renders one platform website section.
 *
 * Covers every `section_type_id` and every `layout_variant` declared in
 * python/core/platform_core/website/section_registry.py. Anything the
 * generator can legally emit must render here — a visitor must never see
 * "Unsupported section type".
 *
 * No LOCAH brand colour appears in this file. Presentation is driven entirely
 * by the `--site-*` CSS custom properties written onto the site root from the
 * business's own theme (see WebsitePageView), so a hotel reads as hospitality
 * and a gym reads as a fitness brand.
 */

type Asset = { url: string; alt_text?: string | null }

/** How a visitor reaches the owner directly — only what the owner published. */
export type SiteContact = { phone?: string; whatsapp?: string; email?: string }

function whatsappHref(number: string, businessName?: string) {
  const digits = number.replace(/\D/g, '')
  const text = businessName ? `?text=${encodeURIComponent(`Hi ${businessName}, `)}` : ''
  return `https://wa.me/${digits}${text}`
}

/** Directions only to somewhere specific — "Jaipur" alone is a city, not a door. */
function findable(address: string) {
  return /\d/.test(address) || address.includes(',') || address.trim().split(/\s+/).length >= 4
}

function mapsHref(address: string) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`
}

/**
 * Call and WhatsApp as real buttons, from the number the owner gave.
 *
 * For most local businesses in India these are the actual conversion paths —
 * nobody fills in a form to ask a furniture shop about a wardrobe. They are
 * plain links from a published fact, not platform mechanics, so they need no
 * module; they appear only when the number exists.
 */
function ContactActions({
  contact,
  businessName,
  onMedia = false,
}: {
  contact?: SiteContact
  businessName?: string
  onMedia?: boolean
}) {
  if (!contact?.phone && !contact?.whatsapp) return null
  const tone = onMedia ? 'ls-btn--ghost-onmedia' : 'ls-btn--outline'
  return (
    <>
      {contact.phone ? (
        <a className={`ls-btn ${tone}`} href={`tel:${contact.phone}`}>
          Call now
        </a>
      ) : null}
      {contact.whatsapp ? (
        <a
          className={`ls-btn ${tone} ls-btn--whatsapp`}
          href={whatsappHref(contact.whatsapp, businessName)}
          target="_blank"
          rel="noopener noreferrer"
        >
          WhatsApp
        </a>
      ) : null}
    </>
  )
}

/** The part of a headline set in the brand colour, when there is one. */
function Accented({ text, accent }: { text: string; accent: string }) {
  if (!accent || !text.includes(accent)) return <>{text}</>
  const at = text.indexOf(accent)
  return (
    <>
      {text.slice(0, at)}
      <span className="ls-accent">{accent}</span>
      {text.slice(at + accent.length)}
    </>
  )
}

/**
 * A section heading: a small category label above a statement.
 *
 * When the title is only the category ("What we do"), the label would repeat
 * it, so it is left out. When the title says something ("Wardrobes built for
 * your room"), the label says what kind of section this is.
 */
function Heading({
  eyebrow,
  title,
  subtitle,
  center = false,
}: {
  eyebrow: string
  title: string
  subtitle?: string
  center?: boolean
}) {
  if (!title) return null
  const showEyebrow = eyebrow && eyebrow.toLowerCase() !== title.toLowerCase()
  return (
    <div className={`ls-head ${center ? 'ls-head--center' : ''}`}>
      {showEyebrow ? <p className="ls-eyebrow">{eyebrow}</p> : null}
      <h2 className="ls-title">{title}</h2>
      {subtitle ? <p className="ls-sub">{subtitle}</p> : null}
    </div>
  )
}

type Item = { title: string; body: string }
type Stat = { value: string; label: string }

function items(v: unknown): Item[] {
  if (!Array.isArray(v)) return []
  return v
    .map((row) => (row && typeof row === 'object' ? (row as Record<string, unknown>) : {}))
    .map((row) => ({ title: str(row.title), body: str(row.body) }))
    .filter((row) => row.title)
}

function stats(v: unknown): Stat[] {
  if (!Array.isArray(v)) return []
  return v
    .map((row) => (row && typeof row === 'object' ? (row as Record<string, unknown>) : {}))
    .map((row) => ({ value: str(row.value), label: str(row.label) }))
    .filter((row) => row.value && row.label)
}

type Section = {
  id: string
  section_type_id: string
  layout_variant?: string | null
  content: Record<string, unknown>
  assets?: Record<string, Asset>
}

function str(v: unknown): string {
  return v === null || v === undefined ? '' : String(v)
}

function bool(v: unknown): boolean {
  return v === true || v === 'true'
}

function num(v: unknown): number | undefined {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : undefined
}

function strArray(v: unknown): string[] | undefined {
  return Array.isArray(v) ? v.map(String).filter(Boolean) : undefined
}

/** Section paths are always relative to the tenant, never absolute. */
function pathHref(slug: string, path: string) {
  if (!path || path === '/') return `/${slug}`
  // An in-page anchor ("#contact") stays on the page the visitor is reading.
  if (path.startsWith('#')) return path
  if (/^https?:\/\//i.test(path)) return path
  const cleaned = path.startsWith('/') ? path.slice(1) : path
  return `/${slug}/${cleaned}`
}

/** No `theme` prop: the business's theme reaches every section through the
 *  `--site-*` custom properties set once on the page wrapper, so sections never
 *  need to read colours in JavaScript. */
export function SectionRenderer({
  section,
  businessSlug,
  index = 0,
  capabilities,
  contact,
  businessName,
  previewToken,
}: {
  section: Section
  businessSlug: string
  /** Position on the page — used only to alternate section grounds. */
  index?: number
  /** The business's live capabilities, so a section never offers an action the
   *  business cannot fulfil. Absent means "unknown", which is treated as off. */
  capabilities?: Record<string, boolean>
  /** Direct contact the owner published. Absent means none. */
  contact?: SiteContact
  businessName?: string
  previewToken?: string
}) {
  const c = section.content || {}
  const v = str(section.layout_variant) || undefined
  const assets = section.assets || {}
  const image = assets.image_asset_id
  // Alternate grounds so a long page has rhythm instead of one flat field.
  const alt = index > 0 && index % 2 === 1

  switch (section.section_type_id) {
    /* ------------------------------------------------------------ hero */
    case 'hero': {
      const variant = v || 'centered'
      const split = variant === 'image_left' || variant === 'image_right'
      const headline = str(c.headline)
      const accent = str(c.headline_accent)
      const eyebrow = str(c.eyebrow)
      const sub = str(c.subheadline)
      const ctaLabel = str(c.cta_label)
      const ctaPath = str(c.cta_url || c.cta_path)
      const onMedia = !split && Boolean(image)
      const actions =
        (ctaLabel && ctaPath) || contact?.phone || contact?.whatsapp ? (
          <div className="ls-hero__cta">
            {ctaLabel && ctaPath ? (
              <Link
                className={`ls-btn ${onMedia ? 'ls-btn--onmedia' : ''}`}
                href={withPreviewToken(pathHref(businessSlug, ctaPath), previewToken)}
              >
                {ctaLabel}
              </Link>
            ) : null}
            <ContactActions
              contact={contact}
              businessName={businessName}
              onMedia={onMedia || !split}
            />
          </div>
        ) : null
      const copy = (
        <>
          {eyebrow ? <p className="ls-hero__eyebrow">{eyebrow}</p> : null}
          <h1 className="ls-hero__headline">
            <Accented text={headline} accent={accent} />
          </h1>
          {sub ? <p className="ls-hero__sub">{sub}</p> : null}
          {actions}
        </>
      )

      if (split) {
        return (
          <section className={`ls-hero ls-hero--${variant} ${image ? '' : 'ls-hero--noimage'}`}>
            <div className="ls-hero__inner">{copy}</div>
            <div className="ls-hero__media">
              {image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={image.url} alt={image.alt_text || ''} />
              ) : (
                <span className="ls-hero__monogram" aria-hidden="true">
                  {(businessName || headline).trim().charAt(0)}
                </span>
              )}
            </div>
          </section>
        )
      }

      return (
        <section
          className={`ls-hero ls-hero--${variant} ${image ? 'ls-hero--hasimage' : 'ls-hero--noimage'}`}
          style={image ? { backgroundImage: `url(${image.url})` } : undefined}
        >
          <div className="ls-hero__inner">{copy}</div>
        </section>
      )
    }

    /* ----------------------------------------------------------- about */
    case 'about': {
      const variant = v || (image ? 'image_right' : 'text_only')
      const title = str(c.title)
      const body = str(c.body)

      if (variant === 'text_only' || !image) {
        return (
          <section className={`ls-section ls-about--text_only ${alt ? 'ls-section--alt' : ''}`}>
            <div className="ls-inner ls-inner--prose">
              <Heading eyebrow="About" title={title} />
              <p className="ls-about__body">{body}</p>
            </div>
          </section>
        )
      }

      return (
        <section className={`ls-section ls-about--${variant} ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner">
            <div className="ls-about__split">
              <div className="ls-about__media">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={image.url} alt={image.alt_text || title} />
              </div>
              <div>
                <Heading eyebrow="About" title={title} />
                <p className="ls-about__body" style={{ marginTop: '1rem' }}>
                  {body}
                </p>
              </div>
            </div>
          </div>
        </section>
      )
    }

    /* ------------------------------------------------------ text_block */
    case 'text_block': {
      const variant = v || 'default'
      const title = str(c.title)
      return (
        <section className={`ls-section ls-text--${variant} ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner ls-inner--prose">
            <div className="ls-text__wrap">
              {title ? (
                <div className="ls-head">
                  <h2 className="ls-title">{title}</h2>
                </div>
              ) : null}
              <p className="ls-text__body">{str(c.body)}</p>
            </div>
          </div>
        </section>
      )
    }

    /* -------------------------------------------------------- cta_band */
    case 'cta_band': {
      const variant = v || 'centered'
      const ctaLabel = str(c.cta_label)
      const ctaPath = str(c.cta_url || c.cta_path)
      // A band with nothing to press is a banner with no point.
      if (!(ctaLabel && ctaPath) && !contact?.phone && !contact?.whatsapp) return null
      return (
        <section className={`ls-cta ls-cta--${variant}`}>
          <div className="ls-cta__inner">
            <div>
              <h2 className="ls-cta__headline">{str(c.headline)}</h2>
              {c.body ? <p className="ls-cta__body">{str(c.body)}</p> : null}
            </div>
            <div className="ls-cta__actions">
              {ctaLabel && ctaPath ? (
                <Link
                  className="ls-btn ls-btn--onmedia"
                  href={withPreviewToken(pathHref(businessSlug, ctaPath), previewToken)}
                >
                  {ctaLabel}
                </Link>
              ) : null}
              <ContactActions contact={contact} businessName={businessName} onMedia />
            </div>
          </div>
        </section>
      )
    }

    /* --------------------------------------------------------- contact */
    case 'contact': {
      const variant = v || 'full'
      const address = str(c.address)
      const phone = str(c.phone)
      const email = str(c.email)
      const hours = str(c.hours_summary)
      const showMap = bool(c.show_map) && address

      return (
        <section
          id="contact"
          className={`ls-section ls-contact--${variant} ${alt ? 'ls-section--alt' : ''}`}
        >
          <div className="ls-inner">
            <Heading eyebrow="Get in touch" title={str(c.title) || 'Visit us'} />
            <div className="ls-contact__actions">
              <ContactActions contact={contact} businessName={businessName} />
              {findable(address) ? (
                <a
                  className="ls-btn ls-btn--outline"
                  href={mapsHref(address)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Get directions
                </a>
              ) : null}
            </div>
            <div className="ls-contact__grid">
              <ul className="ls-contact__list">
                {address ? (
                  <li className="ls-contact__item">
                    <span className="ls-contact__label">Address</span>
                    <span className="ls-contact__value">{address}</span>
                  </li>
                ) : null}
                {phone ? (
                  <li className="ls-contact__item">
                    <span className="ls-contact__label">Phone</span>
                    <span className="ls-contact__value">
                      <a href={`tel:${phone.replace(/\s+/g, '')}`}>{phone}</a>
                    </span>
                  </li>
                ) : null}
                {email ? (
                  <li className="ls-contact__item">
                    <span className="ls-contact__label">Email</span>
                    <span className="ls-contact__value">
                      <a href={`mailto:${email}`}>{email}</a>
                    </span>
                  </li>
                ) : null}
                {hours ? (
                  <li className="ls-contact__item">
                    <span className="ls-contact__label">Hours</span>
                    <span className="ls-contact__value">{hours}</span>
                  </li>
                ) : null}
              </ul>
              {showMap ? (
                <div className="ls-map">
                  <iframe
                    title="Map"
                    loading="lazy"
                    referrerPolicy="no-referrer-when-downgrade"
                    src={`https://www.google.com/maps?q=${encodeURIComponent(address)}&output=embed`}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </section>
      )
    }

    /* ------------------------------------------------------ highlights */
    case 'highlights': {
      const rows = stats(c.items)
      if (rows.length < 2) return null
      const variant = v || 'strip'
      return (
        <section className={`ls-highlights ls-highlights--${variant}`} aria-label="At a glance">
          <div className="ls-inner">
            {c.title ? <Heading eyebrow="At a glance" title={str(c.title)} center /> : null}
            <dl className="ls-highlights__list">
              {rows.map((row, i) => (
                <div key={i} className="ls-highlights__item">
                  <dt className="ls-highlights__value">{row.value}</dt>
                  <dd className="ls-highlights__label">{row.label}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      )
    }

    /* ---------------------------------------------------- feature_grid */
    case 'feature_grid': {
      const rows = items(c.items)
      if (rows.length === 0) return null
      const variant = v || 'cards'
      const eyebrow = variant === 'steps' ? 'How it works' : 'What we do'
      return (
        <section
          className={`ls-section ls-features ls-features--${variant} ${alt ? 'ls-section--alt' : ''}`}
        >
          <div className="ls-inner">
            <Heading
              eyebrow={eyebrow}
              title={str(c.title) || eyebrow}
              subtitle={c.subtitle ? str(c.subtitle) : undefined}
            />
            {variant === 'steps' ? (
              <ol className="ls-steps">
                {rows.map((row, i) => (
                  <li key={i} className="ls-step">
                    <span className="ls-step__n" aria-hidden="true">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <h3 className="ls-step__title">{row.title}</h3>
                    {row.body ? <p className="ls-step__body">{row.body}</p> : null}
                  </li>
                ))}
              </ol>
            ) : (
              <ul
                className={`ls-feature-grid ls-feature-grid--${variant}`}
                data-count={rows.length}
              >
                {rows.map((row, i) => (
                  <li key={i} className="ls-feature">
                    <h3 className="ls-feature__title">{row.title}</h3>
                    {row.body ? <p className="ls-feature__body">{row.body}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )
    }

    /* ---------------------------------------------------- enquiry_form */
    case 'enquiry_form': {
      // Leads currently has no anonymous public mutation route. Rendering a
      // form that posts to a plausible URL would promise a mechanic that does
      // not exist, so governed generation omits it and legacy drafts fail shut.
      return null
    }

    /* --------------------------------------------------------- gallery */
    case 'gallery': {
      const variant = v || 'grid'
      // Gallery images arrive as indexed asset keys resolved by the API.
      const images = Object.entries(assets)
        .filter(([key]) => key.startsWith('image_asset_id'))
        .map(([, a]) => a)
      if (images.length === 0) return null
      return (
        <section className={`ls-section ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner">
            {c.title ? (
              <div className="ls-head ls-head--center">
                <h2 className="ls-title">{str(c.title)}</h2>
              </div>
            ) : null}
            <div className={`ls-gallery ls-gallery--${variant}`}>
              {images.map((img, i) => (
                <figure key={i} className="ls-gallery__item" style={{ margin: 0 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={img.url} alt={img.alt_text || ''} loading="lazy" />
                </figure>
              ))}
            </div>
          </div>
        </section>
      )
    }

    /* -------------------------------------- live record list sections */
    case 'offerings_list':
      return (
        <LiveItemsSection
          capabilities={capabilities}
          businessSlug={businessSlug}
          kind="offerings"
          title={str(c.title) || 'What we offer'}
          subtitle={c.subtitle ? str(c.subtitle) : undefined}
          variant={v}
          maxItems={num(c.max_items)}
          offeringTypes={strArray(c.offering_types)}
          altGround={alt}
        />
      )

    case 'menu_section':
      return (
        <LiveItemsSection
          capabilities={capabilities}
          businessSlug={businessSlug}
          kind="menu"
          title={str(c.title) || 'Menu'}
          variant={v}
          showPrices={c.show_prices === undefined ? true : bool(c.show_prices)}
          offeringTypes={c.category_filter ? [str(c.category_filter)] : undefined}
          altGround={alt}
        />
      )

    case 'plans_section':
      return (
        <LiveItemsSection
          capabilities={capabilities}
          businessSlug={businessSlug}
          kind="plans"
          title={str(c.title) || 'Membership plans'}
          subtitle={c.subtitle ? str(c.subtitle) : undefined}
          variant={v}
          altGround={alt}
        />
      )

    case 'rooms_section':
      return (
        <LiveItemsSection
          capabilities={capabilities}
          businessSlug={businessSlug}
          kind="rooms"
          title={str(c.title) || 'Rooms & suites'}
          subtitle={c.subtitle ? str(c.subtitle) : undefined}
          variant={v}
          sectionClass={`ls-rooms--${v || 'list'}`}
          altGround={alt}
        />
      )

    case 'classes_section':
      return (
        <LiveItemsSection
          capabilities={capabilities}
          businessSlug={businessSlug}
          kind="classes"
          title={str(c.title) || 'Classes'}
          variant={v}
          maxItems={num(c.max_items)}
          altGround={alt}
        />
      )

    /* --------------------------------------------------- location_list */
    case 'location_list': {
      const variant = v || 'cards'
      const locations = Array.isArray((c as { locations?: unknown }).locations)
        ? (c as { locations: Array<Record<string, unknown>> }).locations
        : []
      if (locations.length === 0) return null
      return (
        <section className={`ls-section ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner">
            <div className="ls-head">
              <h2 className="ls-title">{str(c.title) || 'Where to find us'}</h2>
            </div>
            <div className={`ls-locs--${variant}`}>
              {locations.map((loc, i) => (
                <div key={str(loc.id) || i} className="ls-loc">
                  <h3 className="ls-loc__name">
                    {str(loc.name)}
                    {bool(loc.is_primary) ? <span className="ls-loc__primary">Main</span> : null}
                  </h3>
                  {loc.address ? <p className="ls-loc__addr">{str(loc.address)}</p> : null}
                  {bool(c.show_hours) && loc.hours_summary ? (
                    <p className="ls-loc__hours">{str(loc.hours_summary)}</p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </section>
      )
    }

    /* ----------------------------------------------------------------- */
    default:
      // A section type the platform added but this renderer predates. Render
      // nothing — a visitor must never read internal type names off a live
      // website. The Workspace editor is where the owner is told about it.
      return null
  }
}
