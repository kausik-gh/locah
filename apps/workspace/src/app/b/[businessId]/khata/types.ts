/** Shapes of the khata / credit book API (Capability Universe §6.2 `ledger`, §14.5). */

export type Ageing = {
  buckets: { key: string; label: string; amount: number }[]
  overdue: number
  oldest_due: string | null
  advance: number
}

export type Account = {
  id: string
  party_type: 'customer' | 'supplier'
  display_name: string
  phone: string | null
  gstin: string | null
  customer_contact_id: string | null
  balance: number
  credit_limit: number | null
  credit_days: number | null
  status: 'active' | 'closed'
  over_limit: boolean
  limit_used_pct: number | null
  notes: string | null
  last_entry_at: string | null
  version: number
  ageing?: Ageing
}

export type Entry = {
  id: string
  seq: number
  kind: string
  kind_label: string
  amount: number
  balance_after: number
  entry_date: string
  due_date: string | null
  method: string | null
  method_label: string | null
  reference: string | null
  note: string | null
  document_id: string | null
  document_number: string | null
  approved_over_limit: boolean
}

export type AccountDetail = Account & { entries: Entry[]; kinds: Record<string, string>; methods: Record<string, string> }

export type AccountList = { accounts: Account[]; totals: { receivable: number; payable: number; overdue: number } }

export const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v)

export const day = (iso: string | null | undefined) =>
  iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

/** What a balance means, in words, for the kind of account. */
export function owes(a: Pick<Account, 'party_type' | 'balance'>): string {
  if (a.balance === 0) return 'Settled'
  if (a.party_type === 'customer') return a.balance > 0 ? `Owes you ${rupees(a.balance)}` : `${rupees(-a.balance)} paid ahead`
  return a.balance > 0 ? `You owe ${rupees(a.balance)}` : `${rupees(-a.balance)} paid ahead`
}
