/** Shapes of the invoicing API (Capability Universe §14). */

export type BillLine = {
  id: string
  offering_id: string | null
  title: string
  hsn_sac: string | null
  unit_label: string | null
  quantity: number
  unit_price: number
  discount: number
  taxable_value: number
  tax_rate: number | null
  cgst: number
  sgst: number
  igst: number
  line_total: number
  returnable_quantity: number
  creditable_amount: number
  /** OK-15: how a rate-priced line was worked out when sold. */
  basis_words?: string | null
}

export type Party = {
  name?: string
  gstin?: string
  address?: string
  state_code?: string
  phone?: string
  email?: string
}

export type Seller = Party & {
  legal_name?: string
  trade_name?: string
  scheme?: 'regular' | 'composition' | 'unregistered'
  declaration?: string
  location_name?: string
}

export type Bill = {
  id: string
  doc_kind: 'tax_invoice' | 'bill_of_supply' | 'bill' | 'credit_note' | 'debit_note'
  kind_label: string
  status: 'draft' | 'issued' | 'cancelled'
  number: string | null
  issue_date: string | null
  due_date: string | null
  overdue: boolean
  source: 'manual' | 'order' | 'pos'
  order_id: string | null
  order_number: string | null
  note_reason: string | null
  restock: boolean
  buyer: Party
  seller: Seller
  place_of_supply: string | null
  place_of_supply_label: string
  intra_state: boolean | null
  reverse_charge: boolean
  prices_include_tax: boolean
  on_account?: boolean
  customer_contact_id?: string | null
  taxable_total: number
  cgst_total: number
  sgst_total: number
  igst_total: number
  tax_total: number
  round_off: number
  grand_total: number
  amount_due: number
  amount_paid: number
  payment_status: 'unpaid' | 'part_paid' | 'paid' | 'not_applicable'
  outstanding: number
  credited: number
  paid_via_order: boolean
  /** Verified money taken on the order this bill came from (advance, cash at pickup). */
  paid_on_order?: number
  notes: string | null
  cancel_reason: string | null
  register_id: string
  lines?: BillLine[]
  payments?: { id: string; amount: number; method: string; method_label: string; reference: string | null; received_on: string }[]
  related?: { id: string; kind_label: string; number: string | null; status: string; amount_due: number; issue_date: string | null }[]
  tax_by_rate?: { rate: number; taxable: number; cgst: number; sgst: number; igst: number }[]
}

export type Registration = {
  id: string
  scheme: 'regular' | 'composition' | 'unregistered'
  gstin: string | null
  legal_name: string
  trade_name: string | null
  state_code: string
  state_label: string
  address: string | null
  composition_declaration: string | null
  status: string
  document: string
}

export type Register = {
  id: string
  location_id: string
  location_name: string | null
  registration_id: string
  code: string
  name: string
  pad: number
  status: string
  sample_number: string
  number_length: number
  too_long: boolean
}

export type Setup = {
  profile: {
    prices_include_tax: boolean
    round_off: boolean
    issue_on: string
    advances_treatment: string | null
    default_due_days: number | null
    terms: string | null
    bank_details: string | null
    ca_confirmed_at: string | null
  } | null
  registrations: Registration[]
  registers: Register[]
  locations: { id: string; name: string; is_primary: boolean; internal_code: string | null }[]
  states: { code: string; name: string }[]
  issue_on_choices: Record<string, string>
  advances_choices: Record<string, string>
  needs: string[]
  ready: boolean
  confirm_with_ca: string[]
}

export const PAYMENT_LABEL: Record<string, string> = {
  unpaid: 'Unpaid', part_paid: 'Part paid', paid: 'Paid', not_applicable: '',
}

export function rupees(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(amount)
}

export function day(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function codeFor(name: string): string {
  const letters = name.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3) || 'REG'
  return `${letters}1`
}
