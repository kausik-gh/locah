import { Anton, Fraunces, Manrope, Noto_Sans_Tamil } from 'next/font/google'

/**
 * Typefaces for tenant websites — and only tenant websites.
 *
 * Every published site used to draw from the same two faces LOCAH's own pages
 * use, so a gym, a hospital and a home kitchen shared one typographic voice
 * and differed mostly by colour. These give each personality its own:
 *
 *   warm     Fraunces        — soft, editorial, a little old-fashioned
 *   bold     Anton           — condensed and loud, set in capitals
 *   clean    Manrope         — plain, modern, confident
 *   premium  Instrument Serif (already loaded by the root layout)
 *
 * Noto Sans Tamil sits behind all of them as a glyph fallback: an owner who
 * describes their business in Tamil sees their own words in a real Tamil
 * face, not whatever the visitor's system happens to substitute.
 *
 * Loaded from this module so the files are only requested by pages that
 * render a tenant site.
 */

export const fraunces = Fraunces({
  subsets: ['latin'],
  display: 'swap',
  style: ['normal', 'italic'],
  variable: '--font-site-warm',
})

export const anton = Anton({
  subsets: ['latin'],
  weight: '400',
  display: 'swap',
  variable: '--font-site-bold',
})

export const manrope = Manrope({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-site-clean',
})

export const notoTamil = Noto_Sans_Tamil({
  subsets: ['tamil'],
  display: 'swap',
  variable: '--font-site-tamil',
})

export const siteFontVariables = [fraunces, anton, manrope, notoTamil]
  .map((font) => font.variable)
  .join(' ')
