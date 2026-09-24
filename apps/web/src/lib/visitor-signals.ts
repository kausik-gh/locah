import { cookies } from 'next/headers'
import type { PlaceParam } from './marketplace-api'

/**
 * What the Marketplace may know about a visitor, read from two first-party
 * cookies that live in their browser:
 *
 *   locah_place  the area they chose: a town, a PIN, or browser coordinates
 *                already rounded to two decimals (about a kilometre).
 *   locah_seen   counts of the category families and categories they opened,
 *                and their last three searches.
 *
 * Nothing is stored on LOCAH's side. The page forwards these to the API to
 * shape one response, and the visitor can clear them from the Marketplace.
 * Nothing sensitive is inferred from them.
 */

export const PLACE_COOKIE = 'locah_place'
export const SEEN_COOKIE = 'locah_seen'

export type StoredPlace = { l: string; n?: string; p?: string }
export type StoredSeen = { f?: Record<string, number>; c?: Record<string, number>; q?: string[] }

function parse<T>(raw: string | undefined): T | null {
  if (!raw) return null
  try {
    return JSON.parse(decodeURIComponent(raw)) as T
  } catch {
    return null
  }
}

const SLUG = /^[a-z0-9-]{1,40}$/
const NEAR = /^-?\d{1,2}\.\d{1,2},-?\d{1,3}\.\d{1,2}$/

export function readPlace(): { label: string; param: PlaceParam } | null {
  const place = parse<StoredPlace>(cookies().get(PLACE_COOKIE)?.value)
  if (!place || typeof place.l !== 'string' || !place.l.trim()) return null
  if (place.n && NEAR.test(place.n)) return { label: place.l.slice(0, 60), param: { near: place.n } }
  if (place.p && place.p.length <= 60) return { label: place.l.slice(0, 60), param: { place: place.p } }
  return null
}

function counts(raw: Record<string, number> | undefined): string | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const parts = Object.entries(raw)
    .filter(([k, v]) => SLUG.test(k) && Number.isFinite(v) && v > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k, v]) => `${k}:${Math.min(50, Math.round(v))}`)
  return parts.length ? parts.join(',') : undefined
}

export function readSeen(): { fam?: string; cat?: string; searched: string[]; any: boolean } {
  const seen = parse<StoredSeen>(cookies().get(SEEN_COOKIE)?.value) || {}
  const fam = counts(seen.f)
  const cat = counts(seen.c)
  const searched = Array.isArray(seen.q)
    ? seen.q.filter((s) => typeof s === 'string' && s.trim()).map((s) => s.slice(0, 60)).slice(0, 3)
    : []
  return { fam, cat, searched, any: Boolean(fam || cat || searched.length) }
}
