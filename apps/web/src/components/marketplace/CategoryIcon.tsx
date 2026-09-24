/**
 * The glyph for a category family. The API names the glyph (see
 * platform_core.business_categories.FAMILY_ICONS); this file only draws it,
 * so a new family needs no change here unless it wants a new drawing.
 */

// The tints familyTint() names are defined with the card styles.
import './listing-card.css'

type Props = { name?: string | null; size?: number; className?: string }

const common = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const GLYPHS: Record<string, JSX.Element> = {
  bowl: (
    <>
      <path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0Z" />
      <path d="M8.5 8c0-1.2 1.2-1.6 1.2-3M12.5 8c0-1.2 1.2-1.6 1.2-3" />
    </>
  ),
  basket: (
    <>
      <path d="M3 10h18l-2 9.5H5L3 10Z" />
      <path d="M7.5 10 11 4.5M16.5 10 13 4.5M9.5 13.5v3M14.5 13.5v3" />
    </>
  ),
  storefront: (
    <>
      <path d="M4 9.5 5.5 4h13L20 9.5M4.5 10v10h15V10" />
      <path d="M4 9.5a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0M10 20v-5h4v5" />
    </>
  ),
  hanger: (
    <>
      <path d="M10 5.5a2 2 0 1 1 2 2v2" />
      <path d="M12 9.5 3 16.5h18l-9-7Z" />
    </>
  ),
  scissors: (
    <>
      <circle cx="6" cy="6.5" r="2.5" />
      <circle cx="6" cy="17.5" r="2.5" />
      <path d="M8.2 7.8 20 17M8.2 16.2 20 7" />
    </>
  ),
  dumbbell: (
    <>
      <path d="M3 10v4M21 10v4M6 7.5v9M18 7.5v9M6 12h12" />
    </>
  ),
  cross: <path d="M9.5 3.5h5v6h6v5h-6v6h-5v-6h-6v-5h6v-6Z" />,
  book: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z" />
      <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5v2M3 12.5h18" />
    </>
  ),
  shield: <path d="M12 3 19.5 6v5.5c0 4.6-3.2 8-7.5 9.5-4.3-1.5-7.5-4.9-7.5-9.5V6L12 3Z" />,
  building: (
    <>
      <path d="M5 21V4h9v17M14 9h5v12M3 21h18" />
      <path d="M8 8h3M8 12h3M8 16h3M16.5 13h.5M16.5 16.5h.5" />
    </>
  ),
  ruler: (
    <>
      <path d="M3 17 17 3l4 4L7 21l-4-4Z" />
      <path d="m7 13 2 2M10 10l2 2M13 7l2 2" />
    </>
  ),
  wrench: (
    <path d="M14.7 6.3a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.7-7.7a4 4 0 0 0-2-2Z" />
  ),
  car: (
    <>
      <path d="M4 16.5V12l2.2-5h11.6L20 12v4.5H4Z" />
      <circle cx="7.5" cy="16.5" r="2" />
      <circle cx="16.5" cy="16.5" r="2" />
      <path d="M4 12h16" />
    </>
  ),
  bed: (
    <>
      <path d="M3 19V6M3 14.5h18V19M21 14.5V12a3 3 0 0 0-3-3h-7v5.5" />
      <circle cx="7" cy="11.5" r="1.8" />
    </>
  ),
  sparkle: (
    <path d="M12 3.5 13.8 10 20.5 12 13.8 14 12 20.5 10.2 14 3.5 12 10.2 10 12 3.5Z" />
  ),
  camera: (
    <>
      <path d="M4 8h3.5L9 5.5h6L16.5 8H20v11H4V8Z" />
      <circle cx="12" cy="13" r="3.2" />
    </>
  ),
  chip: (
    <>
      <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" />
      <path d="M9.5 3.5v3M14.5 3.5v3M9.5 17.5v3M14.5 17.5v3M3.5 9.5h3M3.5 14.5h3M17.5 9.5h3M17.5 14.5h3" />
    </>
  ),
  gear: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" />
    </>
  ),
  boxes: (
    <>
      <path d="M3.5 12.5h8v8h-8zM12.5 12.5h8v8h-8zM8 4h8v8.5H8z" />
    </>
  ),
  truck: (
    <>
      <path d="M3 6.5h11v10H3zM14 10h4l3 3.5v3h-7" />
      <circle cx="7" cy="17.5" r="1.8" />
      <circle cx="17.5" cy="17.5" r="1.8" />
    </>
  ),
  leaf: (
    <>
      <path d="M5 19C5 10.5 10.5 5 20 4c0 9.5-5.5 15-15 15Z" />
      <path d="m5 19 8.5-8.5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="3.8" />
      <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
    </>
  ),
  paw: (
    <>
      <circle cx="7" cy="9.5" r="1.7" />
      <circle cx="11" cy="6.5" r="1.7" />
      <circle cx="15.5" cy="7.5" r="1.7" />
      <circle cx="18" cy="11.5" r="1.7" />
      <path d="M8.5 17.5c0-2.6 2-5 4.5-5s4 2.2 4 4.2c0 1.8-1.3 2.8-3 2.8-1.2 0-1.7-.6-2.7-.6-1 0-1.4.6-2.2.6-.4 0-.6-.4-.6-2Z" />
    </>
  ),
  key: (
    <>
      <circle cx="8" cy="15" r="4" />
      <path d="m11 12 9-9M16.5 6.5l2.5 2.5M14 9l2 2" />
    </>
  ),
  people: (
    <>
      <circle cx="9" cy="8" r="3" />
      <circle cx="17" cy="9.5" r="2.3" />
      <path d="M3.5 19.5c.4-3.4 2.6-5.5 5.5-5.5s5.1 2.1 5.5 5.5M15 14.3c2.8-.4 5 1.4 5.5 4.7" />
    </>
  ),
}

export function CategoryIcon({ name, size = 24, className }: Props) {
  const glyph = GLYPHS[name || ''] || GLYPHS.storefront
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      {...common}
    >
      {glyph}
    </svg>
  )
}

/** One of seven material tints, chosen from the family id so a family keeps
 *  its colour everywhere without anyone keeping a list of families. */
const TINTS = ['haldi', 'neem', 'indigo', 'clay', 'lotus', 'river', 'sand'] as const

export function familyTint(family?: string | null): (typeof TINTS)[number] {
  if (!family) return 'sand'
  let hash = 0
  for (let i = 0; i < family.length; i++) hash = (hash * 31 + family.charCodeAt(i)) >>> 0
  return TINTS[hash % TINTS.length]
}
