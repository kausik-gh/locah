import type { InterviewMedia } from '@platform/contracts'

export type MediaRole = InterviewMedia['role']

/**
 * What the owner just said this picture is.
 *
 * Someone attaching a file has almost always already typed what it is — "this
 * is our logo", "photos of the hospital" — and making them then find that same
 * answer again in a dropdown is the questionnaire we are trying to get rid of.
 *
 * This reads their own words and nothing else. It is deliberately not a model
 * call: it is classification of a sentence the user is still looking at, so a
 * two-second round trip would cost more than it could possibly add, and a wrong
 * guess is worse than no guess. Where the words do not actually say, this
 * returns null and the caller asks one short question instead of assuming.
 */
export function roleFromText(text: string): MediaRole | null {
  const words = text.toLowerCase()
  if (/\b(logo|logotype|wordmark|emblem)\b/.test(words)) return 'logo'
  if (/\b(hero|cover|banner|header|main image|front page|top of)\b/.test(words)) return 'hero'
  if (/\b(product|products|dish|dishes|menu item|items?we sell|what we sell|service photo)\b/.test(words)) {
    return 'offering'
  }
  if (/\b(gallery|more photos|some photos|a few photos)\b/.test(words)) return 'gallery'
  // "photos of our hospital", "our shop", "inside the studio" — the place itself.
  if (/\b(shop|store|studio|clinic|hospital|restaurant|premises|inside|outside|our place|team|staff)\b/.test(words)) {
    return 'business'
  }
  if (/\b(photo|photos|picture|pictures|image|images)\b/.test(words)) return null
  return null
}

/** How the choice is described back to the owner. Never the enum value. */
export const ROLE_LABELS: Record<MediaRole, string> = {
  logo: 'your logo',
  hero: 'the main picture on your site',
  business: 'a photo of your business',
  offering: 'something you sell',
  gallery: 'a gallery photo',
}

export const ROLE_ORDER: MediaRole[] = ['logo', 'hero', 'business', 'offering', 'gallery']
