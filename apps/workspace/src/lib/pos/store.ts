/**
 * What the counter keeps on the device (Capability Universe §14.2): the
 * catalogue with its version stamp, the open shift and its number block, the
 * queue of bills and drawer entries waiting to sync, and held bills. All of it
 * survives a reload; none of it is trusted by the server.
 */

export type Block = { id: string; start: number; end: number; next: number; period: string; prefix: string; pad: number; next_block?: Block }
export type Queued = { client_mutation_id: string; kind: string; payload: Record<string, unknown>; client_created_at: string; label: string; status?: 'waiting' | 'rejected'; reason?: string }
export type Held = { id: string; label: string; at: string; cart: unknown }

const key = (b: string, k: string) => `locah.pos.${b}.${k}`

export function load<T>(business: string, k: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key(business, k))
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export function save(business: string, k: string, value: unknown): void {
  try {
    localStorage.setItem(key(business, k), JSON.stringify(value))
  } catch {
    /* storage full or blocked: the counter keeps working in memory */
  }
}

export function deviceId(): string {
  try {
    let id = localStorage.getItem('locah.pos.device')
    if (!id) {
      id = `pos-${crypto.randomUUID().slice(0, 12)}`
      localStorage.setItem('locah.pos.device', id)
    }
    return id
  } catch {
    return `pos-${Math.random().toString(36).slice(2, 14)}`
  }
}

export function formatNumber(b: Block, value: number): string {
  return [b.prefix, b.period, String(value).padStart(b.pad, '0')].filter(Boolean).join('/')
}

/** Take the next number from the register's blocks, moving to the next block when one runs out. */
export function takeNumber(b: Block | null): { block: Block | null; used: { block_id: string; value: number; number: string } | null } {
  if (!b) return { block: null, used: null }
  let cur: Block = b
  if (cur.next > cur.end) {
    if (!cur.next_block) return { block: cur, used: null }
    cur = cur.next_block
  }
  const used = { block_id: cur.id, value: cur.next, number: formatNumber(cur, cur.next) }
  return { block: { ...cur, next: cur.next + 1 }, used }
}

export function numbersLeft(b: Block | null): number {
  if (!b) return 0
  return Math.max(0, b.end - b.next + 1) + (b.next_block ? Math.max(0, b.next_block.end - b.next_block.next + 1) : 0)
}
