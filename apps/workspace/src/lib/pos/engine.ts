/**
 * The billing engine's arithmetic for the counter (Capability Universe §14),
 * a line-for-line port of platform_core/invoicing/tax_engine.py so the total
 * shown and printed offline is exactly the bill the server issues on sync.
 *
 * All money is integer paise; every rounding is half-up to the paisa, as in
 * the Python engine (Decimal ROUND_HALF_UP). Rates are percentages with up to
 * two decimals, carried as basis points.
 */

export type Scheme = 'regular' | 'composition' | 'unregistered'
export type TaxContext = { scheme: Scheme; inclusive: boolean; intraState: boolean; roundOff: boolean }
export type LineIn = { quantity: number; unitPrice: number; rate: number | null; discount?: number } // rupees in, as entered
export type LineOut = { gross: number; discount: number; taxable: number; rate: number | null; cgst: number; sgst: number; igst: number; total: number; rateMissing: boolean }
export type Bill = { lines: LineOut[]; taxable: number; cgst: number; sgst: number; igst: number; tax: number; roundOff: number; total: number; discount: number }

/** Round num/den half-up to an integer (num ≥ 0, den > 0). */
function div(num: number, den: number): number {
  return Math.floor((2 * num + den) / (2 * den))
}

export const toPaise = (rupees: number): number => Math.round(rupees * 100)
export const toRupees = (paise: number): number => paise / 100

function bp(rate: number): number {
  return Math.round(rate * 100)
}

function line(l: LineIn, ctx: TaxContext, extraDiscount: number): LineOut {
  const qtyMilli = Math.round(l.quantity * 1000)
  const gross = div(toPaise(l.unitPrice) * qtyMilli, 1000)
  const discount = Math.min(toPaise(l.discount ?? 0) + extraDiscount, gross)
  const amount = gross - discount
  if (ctx.scheme !== 'regular') return { gross, discount, taxable: amount, rate: null, cgst: 0, sgst: 0, igst: 0, total: amount, rateMissing: false }
  if (l.rate === null) return { gross, discount, taxable: amount, rate: null, cgst: 0, sgst: 0, igst: 0, total: amount, rateMissing: true }
  const r = bp(l.rate)
  if (ctx.inclusive) {
    if (ctx.intraState) {
      const half = div(amount * r, 2 * (10000 + r))
      return { gross, discount, taxable: amount - 2 * half, rate: l.rate, cgst: half, sgst: half, igst: 0, total: amount, rateMissing: false }
    }
    const igst = div(amount * r, 10000 + r)
    return { gross, discount, taxable: amount - igst, rate: l.rate, cgst: 0, sgst: 0, igst, total: amount, rateMissing: false }
  }
  if (ctx.intraState) {
    const half = div(amount * r, 20000)
    return { gross, discount, taxable: amount, rate: l.rate, cgst: half, sgst: half, igst: 0, total: amount + 2 * half, rateMissing: false }
  }
  const igst = div(amount * r, 10000)
  return { gross, discount, taxable: amount, rate: l.rate, cgst: 0, sgst: 0, igst, total: amount + igst, rateMissing: false }
}

/** Share a bill-level discount across lines by value; the last line takes the remainder. */
function apportion(amounts: number[], discount: number): number[] {
  const base = amounts.reduce((s, a) => s + a, 0)
  if (discount <= 0 || base <= 0) return amounts.map(() => 0)
  const d = Math.min(discount, base)
  let running = 0
  return amounts.map((a, i) => {
    const share = i === amounts.length - 1 ? d - running : div(d * a, base)
    running += share
    return share
  })
}

export function compute(lines: LineIn[], ctx: TaxContext, billDiscount = 0): Bill {
  const grosses = lines.map((l) => div(toPaise(l.unitPrice) * Math.round(l.quantity * 1000), 1000) - toPaise(l.discount ?? 0))
  const shares = apportion(grosses, toPaise(billDiscount))
  const out = lines.map((l, i) => line(l, ctx, shares[i]))
  const sum = (k: 'taxable' | 'cgst' | 'sgst' | 'igst' | 'discount') => out.reduce((s, x) => s + x[k], 0)
  const taxable = sum('taxable')
  const cgst = sum('cgst')
  const sgst = sum('sgst')
  const igst = sum('igst')
  const payable = taxable + cgst + sgst + igst
  const total = ctx.roundOff ? Math.floor((payable + 50) / 100) * 100 : payable
  return { lines: out, taxable, cgst, sgst, igst, tax: cgst + sgst + igst, roundOff: total - payable, total, discount: sum('discount') }
}

export function rupees(paise: number): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(paise / 100)
}
