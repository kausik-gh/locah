export type Lens = { key: 'weighed' | 'batches' | 'serials' | 'variants' | 'ingredients' | 'counter'; title: string; primary_action: string; empty: string }

export type StockProfile = {
  lenses: Lens[]
  primary: Lens['key']
  yield_offered: boolean
  wastage_reasons: { key: string; label: string }[]
  configured: Record<string, number>
  because: { traits: string[]; playbook_hints: string[]; family: string | null }
  can: { adjust: boolean; approve: boolean; cost: boolean; setup: boolean }
}

export type StockRow = {
  id: string
  offering_id: string
  variant_id: string | null
  location_id: string
  title: string
  sku: string | null
  kind: string
  stock_unit: 'piece' | 'g' | 'ml'
  variant: string | null
  variant_attributes: Record<string, string> | null
  quantity_on_hand: number
  quantity_reserved: number
  quantity_available: number
  on_hand_text: string
  available_text: string
  stock_status: 'available' | 'low_stock' | 'out_of_stock'
  reorder_min: number | null
  reorder_max: number | null
  reorder_suggest: number | null
  reorder_suggest_text: string | null
  buy_units: { label: string; quantity: number }[]
  batch_tracked: boolean
  serial_tracked: boolean
  warranty_months: number | null
  batches: number
  next_expiry: string | null
  expiring_30d: number
  expired: number
  serials_in_stock: number
  last_counted_at: string | null
  value_paise?: number
  average_cost_paise?: number | null
}

export type StockOverview = {
  items: StockRow[]
  totals: { items: number; low: number; out: number; expiring_30d: number; expired: number; value_paise?: number; not_valued?: number }
}

export type StockItem = {
  id: string
  title: string
  kind: string
  stock_unit: 'piece' | 'g' | 'ml'
  track_inventory: boolean
  batch_tracked: boolean
  serial_tracked: boolean
  warranty_months: number | null
  buy_units: { label: string; quantity: number }[]
  variant_options: { name: string; values: string[] }[]
  variants: { id: string; name: string; attributes: Record<string, string> }[]
}

export type Batch = {
  id: string; inventory_record_id: string; offering_id: string; title: string; location_id: string
  batch_code: string; expires_on: string | null; received_on: string; quantity_on_hand: number
  quantity_text: string; quantity_received: number; status: string; days_left?: number; state?: 'expired' | 'today' | 'soon'
}

export type YieldRow = {
  id: string; source_offering_id: string; source_title: string; output_offering_id: string; output_title: string
  yield_bp: number; yield_percent: number; note: string | null; runs: number; actual_percent_of_expected: number | null
}

export type Conversion = {
  id: string; source_title: string | null; source_text: string; trim_text: string; trim_percent: number; at: string | null
  outputs: { offering_id: string; title: string; actual: number; actual_text: string; expected: number | null; expected_text: string | null }[]
}

export type Wastage = {
  days: number
  reasons: { reason: string; label: string; entries: number; quantities: string[]; value_paise?: number }[]
  cutting: { runs: number; trim_percent: number | null }
}

export type Location = { id: string; name: string; is_primary: boolean }

export type CountSummary = { id: string; location_id: string; label: string; status: 'open' | 'submitted' | 'approved' | 'cancelled'; submitted_at: string | null; decided_at: string | null; decision_note: string | null; created_at: string | null }

/** Grams as kg, millilitres as litres — how people at a counter talk about stock. */
export const UNIT: Record<StockItem['stock_unit'], { word: string; per: number; step: string }> = {
  g: { word: 'kg', per: 1000, step: '0.001' },
  ml: { word: 'L', per: 1000, step: '0.001' },
  piece: { word: 'pcs', per: 1, step: '1' },
}

export const toStock = (value: string, unit: StockItem['stock_unit']): number => Math.round(Number(value || 0) * UNIT[unit].per)

export const rupees = (paise: number): string =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)
