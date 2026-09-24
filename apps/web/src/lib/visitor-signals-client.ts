/** Browser half of visitor-signals.ts: the only code that writes the cookies. */

import type { StoredPlace, StoredSeen } from './visitor-signals'

const PLACE_COOKIE = 'locah_place'
const SEEN_COOKIE = 'locah_seen'

function write(name: string, value: unknown, days: number) {
  const secure = window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `${name}=${encodeURIComponent(JSON.stringify(value))}; Path=/; Max-Age=${
    days * 86400
  }; SameSite=Lax${secure}`
}

function clear(name: string) {
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`
}

function read<T>(name: string): T | null {
  const hit = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))
  if (!hit) return null
  try {
    return JSON.parse(decodeURIComponent(hit.slice(name.length + 1))) as T
  } catch {
    return null
  }
}

export function savePlace(place: StoredPlace) {
  write(PLACE_COOKIE, place, 90)
}

export function clearPlace() {
  clear(PLACE_COOKIE)
}

export function rememberBrowse(signal: { family?: string | null; category?: string | null; q?: string | null }) {
  const seen = read<StoredSeen>(SEEN_COOKIE) || {}
  const bump = (bucket: Record<string, number> | undefined, key?: string | null) => {
    const next = { ...(bucket || {}) }
    if (key) next[key] = Math.min(50, (next[key] || 0) + 1)
    // Keep the eight strongest; the cookie stays small.
    return Object.fromEntries(Object.entries(next).sort((a, b) => b[1] - a[1]).slice(0, 8))
  }
  const q = (signal.q || '').trim().slice(0, 60)
  write(
    SEEN_COOKIE,
    {
      f: bump(seen.f, signal.family),
      c: bump(seen.c, signal.category),
      q: q ? [q, ...(seen.q || []).filter((s) => s.toLowerCase() !== q.toLowerCase())].slice(0, 3) : seen.q || [],
    },
    30
  )
}

export function forgetBrowse() {
  clear(SEEN_COOKIE)
}
