import {
  Anton,
  Archivo,
  Bricolage_Grotesque,
  Cormorant_Garamond,
  DM_Sans,
  Fraunces,
  IBM_Plex_Mono,
  IBM_Plex_Sans,
  Manrope,
  Newsreader,
  Noto_Sans_Tamil,
  Outfit,
  Playfair_Display,
} from 'next/font/google'

/**
 * Typefaces for tenant websites — and only tenant websites.
 *
 * Every published site used to draw from the same two faces LOCAH's own pages
 * use, so a gym, a hospital and a home kitchen shared one typographic voice
 * and differed mostly by colour. A site's type system is part of its creative
 * direction (see platform_core.interview.creative_director):
 *
 *   editorial_food     Playfair Display over DM Sans — a food brand's serif
 *   bold_commerce      Archivo, heavy, over DM Sans — a shop that means business
 *   cinematic_fitness  Archivo, black and expanded, set in capitals
 *   premium_property   Outfit — confident geometric sans, airy
 *   technical_b2b      IBM Plex Sans — precise, engineered
 *   calm_care          Manrope — plain, calm, clear
 *   friendly_local     Fraunces over Manrope — warm and local
 *
 * Design system v3 adds four faces for families the first seven could not voice:
 *
 *   premium_serif         Cormorant Garamond over Manrope — quiet luxury
 *   playful_grotesk       Bricolage Grotesque — characterful, friendly
 *   portfolio_serif       Newsreader, with IBM Plex Mono captions — a work notebook
 *   technical_mono        IBM Plex Sans with Plex Mono specs
 *   monumental_condensed  Anton over Outfit — poster weight
 *   modern_grotesk        Archivo at normal width over DM Sans
 *   calm_serif            Fraunces (soft) over Manrope
 *
 * Older personalities keep their faces (Fraunces, Anton, Manrope). None of
 * these is LOCAH's own brand face. Noto Sans Tamil sits behind all of them as
 * a glyph fallback: an owner who writes in Tamil sees a real Tamil face.
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

export const playfair = Playfair_Display({
  subsets: ['latin'],
  display: 'swap',
  style: ['normal', 'italic'],
  variable: '--font-site-playfair',
})

export const dmSans = DM_Sans({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-site-dm',
})

export const archivo = Archivo({
  subsets: ['latin'],
  display: 'swap',
  axes: ['wdth'],
  variable: '--font-site-archivo',
})

export const outfit = Outfit({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-site-outfit',
})

export const plex = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-site-plex',
})

export const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  style: ['normal', 'italic'],
  display: 'swap',
  variable: '--font-site-cormorant',
})

export const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-site-bricolage',
})

export const newsreader = Newsreader({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  display: 'swap',
  variable: '--font-site-newsreader',
})

export const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
  variable: '--font-site-mono',
})

export const notoTamil = Noto_Sans_Tamil({
  subsets: ['tamil'],
  display: 'swap',
  variable: '--font-site-tamil',
})

export const siteFontVariables = [
  fraunces,
  anton,
  manrope,
  playfair,
  dmSans,
  archivo,
  outfit,
  plex,
  cormorant,
  bricolage,
  newsreader,
  plexMono,
  notoTamil,
]
  .map((font) => font.variable)
  .join(' ')
