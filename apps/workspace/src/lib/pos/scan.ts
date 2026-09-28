/**
 * Codes at the counter (Capability Universe §14.3), resolved from the cached
 * catalogue so scanning works offline: a GTIN or in-store barcode, the item's
 * own code (SKU), or a weighed-goods label decoded with the business's scale
 * format (set in Settings → Counter billing; never assumed).
 */

export type PosVariant = { id: string; name: string; sku: string | null; barcode: string | null; price: number; available: number | null }
export type PosPack = { label: string; price: number; stock_per_unit: number }
export type PosItem = {
  id: string
  title: string
  kind: string
  price: number
  sku: string | null
  barcode: string | null
  hsn_sac: string | null
  rate: number | null
  stock_unit: string
  price_per: string | null
  track_inventory: boolean
  available: number | null
  packs: PosPack[]
  variants: PosVariant[]
  /** Units in stock here by serial/IMEI (§15.1); the counter captures one per unit sold. */
  serial_tracked?: boolean
  serials?: string[]
}
export type WeighedFormat = { prefix: string; item_digits: number; value: 'weight' | 'price'; value_digits: number; value_decimals: number }

export type ScanHit = { item: PosItem; variant?: PosVariant; quantity?: number; price?: number; serial?: string }

export function gtinOk(code: string): boolean {
  if (!/^\d+$/.test(code) || ![8, 12, 13, 14].includes(code.length)) return false
  const d = code.split('').map(Number)
  const check = d.pop() as number
  const total = d.reverse().reduce((s, x, i) => s + x * (i % 2 === 0 ? 3 : 1), 0)
  return (10 - (total % 10)) % 10 === check
}

export function resolveCode(raw: string, items: PosItem[], fmt: WeighedFormat | null): ScanHit | null {
  const code = raw.trim()
  if (!code) return null
  if (fmt && code.length === fmt.prefix.length + fmt.item_digits + fmt.value_digits + 1 && code.startsWith(fmt.prefix) && /^\d+$/.test(code)) {
    if (!gtinOk(code)) return null
    const at = fmt.prefix.length
    const itemCode = code.slice(at, at + fmt.item_digits)
    const value = Number(code.slice(at + fmt.item_digits, at + fmt.item_digits + fmt.value_digits)) / 10 ** fmt.value_decimals
    const item = items.find((i) => i.sku === itemCode)
    if (item) {
      if (fmt.value === 'weight') return { item, quantity: value }
      // A price label: the quantity is what that price buys at the item's rate.
      return { item, quantity: Math.round((value / item.price) * 1000) / 1000 }
    }
  }
  const upper = code.toUpperCase()
  for (const item of items) {
    if (item.serial_tracked && item.serials?.includes(upper)) return { item, serial: upper }
  }
  for (const item of items) {
    if (item.barcode === code || item.sku === code) return { item }
    const v = item.variants.find((x) => x.barcode === code || x.sku === code)
    if (v) return { item, variant: v }
  }
  return null
}
