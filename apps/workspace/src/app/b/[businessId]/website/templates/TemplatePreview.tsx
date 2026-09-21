import type { CSSProperties } from 'react'

/**
 * A truthful miniature of what a template actually builds.
 *
 * Not a screenshot, and deliberately not a picture of a different website. It
 * draws the template's own composition: the real sections, in the real order,
 * each one as the silhouette of the variant it actually uses, in the template's
 * real palette, with the radius its personality really produces. A hero that
 * runs full-bleed and one that sits left-aligned are the same section type and
 * not remotely the same page, so the variant is what gets drawn.
 *
 * It renders as plain elements with no images, no JavaScript and no network —
 * eight of these sit on one screen, and a picker that costs eight screenshots
 * to open is a picker nobody waits for.
 */

export type PreviewSection = {
  section_type_id: string
  layout_variant?: string | null
}

type Palette = {
  primary: string
  accent: string
  radius: string
}

function paletteFor(personality: string, primary: string, accent: string): Palette {
  // The same radii the site tokens produce for each personality, so the
  // miniature is not quietly softer or sharper than the thing it describes.
  const radius =
    personality === 'premium'
      ? '1px'
      : personality === 'warm'
        ? '4px'
        : personality === 'bold'
          ? '2px'
          : '3px'
  return { primary, accent, radius }
}

/** A run of text lines. The workhorse: most sections are type and space. */
function Lines({
  count,
  align = 'left',
  widths,
  tone = 'ink',
}: {
  count: number
  align?: 'left' | 'center'
  widths?: number[]
  tone?: 'ink' | 'onDark'
}) {
  const fallback = [92, 78, 60]
  return (
    <div className="tplp-lines" data-align={align}>
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className="tplp-line"
          data-tone={tone}
          style={{ width: `${(widths ?? fallback)[i % (widths ?? fallback).length]}%` }}
        />
      ))}
    </div>
  )
}

function Tiles({ count, cols, ratio = 1 }: { count: number; cols: number; ratio?: number }) {
  return (
    <div className="tplp-tiles" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} className="tplp-tile" style={{ aspectRatio: String(ratio) }} />
      ))}
    </div>
  )
}

/**
 * One section, drawn as itself.
 *
 * Anything without a specific silhouette falls back to a titled block rather
 * than disappearing — a preview that silently omits a section would misdescribe
 * the template, which is the one thing this component must not do.
 */
function Section({ section, palette }: { section: PreviewSection; palette: Palette }) {
  const { section_type_id: type, layout_variant: variant } = section
  const accentBar = <span className="tplp-rule" style={{ background: palette.accent }} />

  if (type === 'hero') {
    if (variant === 'full_width') {
      return (
        <div className="tplp-hero tplp-hero--bleed" style={{ background: palette.primary }}>
          <Lines count={2} align="center" widths={[70, 44]} tone="onDark" />
          <span className="tplp-btn" style={{ background: palette.accent }} />
        </div>
      )
    }
    if (variant === 'image_left' || variant === 'image_right') {
      return (
        <div className="tplp-split" data-flip={variant === 'image_left' || undefined}>
          <div className="tplp-pane">
            <Lines count={2} widths={[88, 58]} />
            <span className="tplp-btn" style={{ background: palette.primary }} />
          </div>
          <span className="tplp-img" />
        </div>
      )
    }
    const align = variant === 'centered' ? 'center' : 'left'
    return (
      <div className="tplp-hero" style={{ borderColor: palette.primary }}>
        <Lines count={2} align={align} widths={[76, 50]} />
        <span
          className="tplp-btn"
          style={{ background: palette.primary, marginInline: align === 'center' ? 'auto' : undefined }}
        />
      </div>
    )
  }

  if (type === 'about' || type === 'text_block') {
    if (variant === 'image_left' || variant === 'image_right') {
      return (
        <div className="tplp-split" data-flip={variant === 'image_left' || undefined}>
          <div className="tplp-pane">
            {accentBar}
            <Lines count={3} />
          </div>
          <span className="tplp-img" />
        </div>
      )
    }
    return (
      <div className="tplp-band" data-highlight={variant === 'highlighted' || undefined}>
        {accentBar}
        <Lines count={3} widths={[96, 90, 64]} />
      </div>
    )
  }

  if (type === 'menu_section') {
    return (
      <div className="tplp-band">
        {accentBar}
        {[0, 1].map((group) => (
          <div key={group} className="tplp-group">
            <span className="tplp-line" style={{ width: '34%' }} data-tone="ink" />
            {[0, 1].map((row) => (
              <div key={row} className="tplp-row">
                <span className="tplp-line" style={{ width: '52%' }} />
                <span className="tplp-price" style={{ background: palette.accent }} />
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  if (type === 'offerings_list' || type === 'rooms_section' || type === 'classes_section') {
    if (variant === 'grid') {
      return (
        <div className="tplp-band">
          {accentBar}
          <Tiles count={6} cols={3} ratio={1.1} />
        </div>
      )
    }
    if (variant === 'list' || variant === 'schedule') {
      return (
        <div className="tplp-band">
          {accentBar}
          {[0, 1, 2].map((row) => (
            <div key={row} className="tplp-row tplp-row--ruled">
              <span className="tplp-line" style={{ width: '46%' }} />
              <span className="tplp-price" style={{ background: palette.accent }} />
            </div>
          ))}
        </div>
      )
    }
    return (
      <div className="tplp-band">
        {accentBar}
        <div className="tplp-cards">
          {[0, 1, 2].map((card) => (
            <div key={card} className="tplp-card" style={{ borderRadius: palette.radius }}>
              <span className="tplp-img tplp-img--card" />
              <span className="tplp-line" style={{ width: '70%' }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (type === 'plans_section') {
    return (
      <div className="tplp-band">
        {accentBar}
        <div className="tplp-cards">
          {[0, 1, 2].map((card) => (
            <div
              key={card}
              className="tplp-card tplp-card--plan"
              data-featured={card === 1 || undefined}
              style={{
                borderRadius: palette.radius,
                borderColor: card === 1 ? palette.primary : undefined,
              }}
            >
              <span className="tplp-line" style={{ width: '54%' }} />
              <span className="tplp-line tplp-line--big" style={{ width: '38%' }} />
              <Lines count={2} widths={[84, 70]} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (type === 'gallery') {
    const masonry = variant === 'masonry'
    return (
      <div className="tplp-band">
        {accentBar}
        <div className="tplp-mosaic" data-masonry={masonry || undefined}>
          {Array.from({ length: masonry ? 5 : 4 }).map((_, i) => (
            <span key={i} className="tplp-tile" />
          ))}
        </div>
      </div>
    )
  }

  if (type === 'cta_band') {
    return (
      <div className="tplp-cta" style={{ background: palette.primary }}>
        <Lines
          count={1}
          align={variant === 'centered' ? 'center' : 'left'}
          widths={[58]}
          tone="onDark"
        />
        <span
          className="tplp-btn"
          style={{
            background: palette.accent,
            marginInline: variant === 'centered' ? 'auto' : undefined,
          }}
        />
      </div>
    )
  }

  if (type === 'contact' || type === 'location_list') {
    return (
      <div className="tplp-split">
        <div className="tplp-pane">
          {accentBar}
          <Lines count={3} widths={[70, 52, 60]} />
        </div>
        <span className="tplp-img tplp-img--map" />
      </div>
    )
  }

  if (type === 'enquiry_form') {
    return (
      <div className="tplp-band">
        {accentBar}
        <span className="tplp-field" style={{ borderRadius: palette.radius }} />
        <span className="tplp-field" style={{ borderRadius: palette.radius }} />
        <span className="tplp-btn" style={{ background: palette.primary }} />
      </div>
    )
  }

  return (
    <div className="tplp-band">
      {accentBar}
      <Lines count={2} />
    </div>
  )
}

export function TemplatePreview({
  sections,
  personality,
  primaryColor,
  accentColor,
  label,
}: {
  sections: PreviewSection[]
  personality: string
  primaryColor: string
  accentColor: string
  label: string
}) {
  const palette = paletteFor(personality, primaryColor, accentColor)
  const style = {
    '--tplp-primary': palette.primary,
    '--tplp-accent': palette.accent,
    '--tplp-radius': palette.radius,
  } as CSSProperties

  return (
    <div
      className="tplp"
      data-personality={personality}
      style={style}
      role="img"
      aria-label={`Layout preview: ${label}`}
    >
      <div className="tplp-chrome">
        <span className="tplp-dot" />
        <span className="tplp-dot" />
        <span className="tplp-dot" />
      </div>
      <div className="tplp-nav">
        <span className="tplp-brand" style={{ background: palette.primary }} />
        <span className="tplp-navlinks">
          <span />
          <span />
          <span />
        </span>
      </div>
      <div className="tplp-body">
        {sections.map((section, i) => (
          <Section key={`${section.section_type_id}-${i}`} section={section} palette={palette} />
        ))}
      </div>
    </div>
  )
}
