'use client'

import { useState, useTransition } from 'react'
import { variantsFor } from './phone-actions'
import { useWsWords } from '@/components/WsWords'

export type CatalogueItem = {
  id: string
  title: string
  price_amount: number | null
  option_groups: { name: string; required: boolean; max: number; choices: { label: string; price_delta: string | number }[]; text?: boolean; max_length?: number }[]
  sell_units: { label: string; qty: number }[]
  variant_options: { name: string; values: string[] }[]
}

export type PickedLine = {
  offering_id: string
  variant_id?: string
  quantity: number
  options?: Record<string, unknown>
  label: string
}

/**
 * Pick an item as the customer asks for it: its pack, size, choices and any
 * written message — the same selections the website sends. The server prices it.
 */
export function ItemPicker({ businessId, items, onAdd }: { businessId: string; items: CatalogueItem[]; onAdd: (l: PickedLine) => void }) {
  const t = useWsWords()
  const [id, setId] = useState(items[0]?.id ?? '')
  const [qty, setQty] = useState('1')
  const [choices, setChoices] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [pack, setPack] = useState('')
  const [variants, setVariants] = useState<{ id: string; name: string }[]>([])
  const [variant, setVariant] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, start] = useTransition()
  const item = items.find((i) => i.id === id)

  const choose = (next: string) => {
    setId(next)
    setChoices({})
    setNotes({})
    setPack('')
    setVariant('')
    setVariants([])
    setError(null)
    const it = items.find((i) => i.id === next)
    if (it?.variant_options?.length) {
      start(async () => {
        const r = await variantsFor(businessId, next)
        if (r.ok) setVariants((r.data ?? []).map((v) => ({ id: v.id, name: v.name })))
      })
    }
  }
  const add = () => {
    if (!item) return
    const n = Number(qty)
    if (!Number.isInteger(n) || n < 1) return setError(t('Enter how many.'))
    const missing = item.option_groups.find((g) => g.required && !g.text && !choices[g.name])
    if (missing) return setError(t('Choose {name}.', { name: missing.name.toLowerCase() }))
    if (item.sell_units?.length && !pack) return setError(t('Choose the pack.'))
    if (variants.length && !variant) return setError(t('Choose the option.'))
    const options: Record<string, unknown> = {}
    const picked = Object.fromEntries(Object.entries(choices).filter(([, v]) => v).map(([k, v]) => [k, [v]]))
    if (Object.keys(picked).length) options.choices = picked
    const written = Object.fromEntries(Object.entries(notes).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()]))
    if (Object.keys(written).length) options.notes = written
    if (pack) options.pack = pack
    const parts = [pack, variants.find((v) => v.id === variant)?.name, ...Object.values(choices).filter(Boolean),
      ...Object.values(written).map((w) => `“${w}”`)].filter(Boolean)
    onAdd({ offering_id: item.id, variant_id: variant || undefined, quantity: n, options: Object.keys(options).length ? options : undefined,
      label: `${item.title}${parts.length ? ` — ${parts.join(' · ')}` : ''}` })
    setQty('1')
    setChoices({})
    setNotes({})
    setError(null)
  }

  if (!items.length) return <p className="bos-hint">{t('No items to sell yet — add them in Products & services.')}</p>
  return (
    <div className="bos-picker">
      <div className="bos-form-grid">
        <label>
          <span className="bos-label">{t('Item')}</span>
          <select name="pick-item" value={id} onChange={(e) => choose(e.target.value)}>
            {items.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
          </select>
        </label>
        {item?.sell_units?.length ? (
          <label>
            <span className="bos-label">{t('Pack')}</span>
            <select name="pick-pack" value={pack} onChange={(e) => setPack(e.target.value)}>
              <option value="">{t('Choose…')}</option>
              {item.sell_units.map((p) => <option key={p.label} value={p.label}>{p.label}</option>)}
            </select>
          </label>
        ) : null}
        {variants.length ? (
          <label>
            <span className="bos-label">{item?.variant_options.map((a) => a.name).join(' / ') || t('Option')}</span>
            <select name="pick-variant" value={variant} onChange={(e) => setVariant(e.target.value)}>
              <option value="">{t('Choose…')}</option>
              {variants.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </label>
        ) : null}
        {(item?.option_groups ?? []).map((g) => g.text ? (
          <label key={g.name}>
            <span className="bos-label">{g.name}{g.required ? '' : ` — ${t('optional')}`}</span>
            <input name={`pick-note-${g.name}`} value={notes[g.name] ?? ''} maxLength={g.max_length ?? 60}
              onChange={(e) => setNotes((n) => ({ ...n, [g.name]: e.target.value }))} />
          </label>
        ) : (
          <label key={g.name}>
            <span className="bos-label">{g.name}{g.required ? '' : ` — ${t('optional')}`}</span>
            <select name={`pick-choice-${g.name}`} value={choices[g.name] ?? ''} onChange={(e) => setChoices((c) => ({ ...c, [g.name]: e.target.value }))}>
              <option value="">{g.required ? t('Choose…') : t('None')}</option>
              {g.choices.map((c) => <option key={c.label} value={c.label}>{c.label}{Number(c.price_delta) ? ` (+₹${Number(c.price_delta)})` : ''}</option>)}
            </select>
          </label>
        ))}
        <label>
          <span className="bos-label">{t('How many')}</span>
          <input name="pick-qty" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />
        </label>
        <div className="bos-picker__add"><button type="button" className="btn-ghost" onClick={add} disabled={pending}>{t('Add to order')}</button></div>
      </div>
      {error ? <p className="bos-error" role="status">{error}</p> : null}
    </div>
  )
}
