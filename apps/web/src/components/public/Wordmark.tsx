/**
 * The LOCAH wordmark.
 *
 * The mark is a pin whose counter is a storefront arch — the two things LOCAH
 * joins: a place, and a business that trades there. Drawn in `currentColor` so
 * it inverts correctly on the navy ground without a second asset.
 *
 * To swap in the supplied brand asset, replace the <svg> with an <img> pointing
 * at a file in `apps/web/public/`; nothing else in the app references the glyph.
 */
export function Wordmark({ size = 26 }: { size?: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.55rem' }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        style={{ flexShrink: 0 }}
      >
        <path
          d="M16 2.5c-5.66 0-10.25 4.48-10.25 10 0 6.9 8.2 15.6 9.47 16.9a1.09 1.09 0 0 0 1.56 0c1.27-1.3 9.47-10 9.47-16.9 0-5.52-4.59-10-10.25-10Z"
          fill="var(--locah-accent, #E8622C)"
        />
        <path
          d="M11 15.5v-2.2l5-3.6 5 3.6v2.2"
          stroke="#fff"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M12.4 15.5v4.4h7.2v-4.4" stroke="#fff" strokeWidth="1.9" strokeLinejoin="round" />
      </svg>
      <span
        style={{
          fontWeight: 600,
          fontSize: '1.14rem',
          letterSpacing: '-0.015em',
        }}
      >
        LOCAH
      </span>
    </span>
  )
}
