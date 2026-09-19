import Link from 'next/link'
import { LiveItemsSection } from './LiveItemsSection'

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
}: {
  section: Section
  businessSlug: string
  /** Position on the page — used only to alternate section grounds. */
  index?: number
  /** The business's live capabilities, so a section never offers an action the
   *  business cannot fulfil. Absent means "unknown", which is treated as off. */
  capabilities?: Record<string, boolean>
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
      const sub = str(c.subheadline)
      const ctaLabel = str(c.cta_label)
      const ctaPath = str(c.cta_url || c.cta_path)

      if (split) {
        return (
          <section className={`ls-hero ls-hero--${variant}`}>
            <div className="ls-hero__inner">
              <h1 className="ls-hero__headline">{headline}</h1>
              {sub ? <p className="ls-hero__sub">{sub}</p> : null}
              {ctaLabel && ctaPath ? (
                <div className="ls-hero__cta">
                  <Link className="ls-btn" href={pathHref(businessSlug, ctaPath)}>
                    {ctaLabel}
                  </Link>
                </div>
              ) : null}
            </div>
            <div className="ls-hero__media">
              {image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={image.url} alt={image.alt_text || ''} />
              ) : null}
            </div>
          </section>
        )
      }

      return (
        <section
          className={`ls-hero ls-hero--${variant} ${image ? 'ls-hero--hasimage' : ''}`}
          style={image ? { backgroundImage: `url(${image.url})` } : undefined}
        >
          <div className="ls-hero__inner">
            <h1 className="ls-hero__headline">{headline}</h1>
            {sub ? <p className="ls-hero__sub">{sub}</p> : null}
            {ctaLabel && ctaPath ? (
              <div className="ls-hero__cta">
                <Link className="ls-btn ls-btn--onmedia" href={pathHref(businessSlug, ctaPath)}>
                  {ctaLabel}
                </Link>
              </div>
            ) : null}
          </div>
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
              {title ? (
                <div className="ls-head">
                  <h2 className="ls-title">{title}</h2>
                </div>
              ) : null}
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
                {title ? <h2 className="ls-title">{title}</h2> : null}
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
      return (
        <section className={`ls-cta ls-cta--${variant}`}>
          <div className="ls-cta__inner">
            <div>
              <h2 className="ls-cta__headline">{str(c.headline)}</h2>
              {c.body ? <p className="ls-cta__body">{str(c.body)}</p> : null}
            </div>
            {ctaLabel && ctaPath ? (
              <Link className="ls-btn ls-btn--onmedia" href={pathHref(businessSlug, ctaPath)}>
                {ctaLabel}
              </Link>
            ) : null}
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
        <section className={`ls-section ls-contact--${variant} ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner">
            <div className="ls-head">
              <h2 className="ls-title">{str(c.title) || 'Visit us'}</h2>
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

    /* ---------------------------------------------------- enquiry_form */
    case 'enquiry_form': {
      const variant = v || 'default'
      // Posts to the tenant's own enquiry route, which creates a Lead via the
      // existing leads module. No fake submission handler.
      return (
        <section className={`ls-section ${alt ? 'ls-section--alt' : ''}`}>
          <div className="ls-inner ls-inner--narrow">
            <div className="ls-head ls-head--center">
              <h2 className="ls-title">{str(c.title) || 'Get in touch'}</h2>
              {c.subtitle ? <p className="ls-sub">{str(c.subtitle)}</p> : null}
            </div>
            <form className={`ls-form ${variant === 'compact' ? 'ls-form--compact' : ''}`} method="post" action={`/${businessSlug}/enquire`}>
              <div className="ls-field">
                <label className="ls-field__label" htmlFor={`nm-${section.id}`}>
                  Your name
                </label>
                <input id={`nm-${section.id}`} name="name" required autoComplete="name" />
              </div>
              <div className="ls-field">
                <label className="ls-field__label" htmlFor={`em-${section.id}`}>
                  Email
                </label>
                <input id={`em-${section.id}`} name="email" type="email" required autoComplete="email" />
              </div>
              <div className="ls-field">
                <label className="ls-field__label" htmlFor={`ph-${section.id}`}>
                  Phone <span style={{ opacity: 0.6 }}>(optional)</span>
                </label>
                <input id={`ph-${section.id}`} name="phone" type="tel" autoComplete="tel" />
              </div>
              {variant !== 'compact' ? (
                <div className="ls-field">
                  <label className="ls-field__label" htmlFor={`ms-${section.id}`}>
                    How can we help?
                  </label>
                  <textarea id={`ms-${section.id}`} name="message" />
                </div>
              ) : null}
              <div className="ls-form__actions">
                <button type="submit" className="ls-btn">
                  Send enquiry
                </button>
                <span className="ls-form__note">We usually reply within a day.</span>
              </div>
            </form>
          </div>
        </section>
      )
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
        ? ((c as { locations: Array<Record<string, unknown>> }).locations)
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
