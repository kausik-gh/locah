'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { makeVariants, saveOffering } from './offering-actions'
import type { Axis, Kind, KindField, Offering, OptionGroup, Pack, Variant } from './types'
import { inr } from './types'

type Attr = Record<string, string | boolean>

function toForm(f: KindField, v: unknown): string | boolean {
  if (f.type === 'bool') return Boolean(v)
  if (f.type === 'list') return Array.isArray(v) ? v.join('\n') : String(v ?? '')
  return v === undefined || v === null ? '' : String(v)
}

/**
 * One editor for every kind of offering (Capability Universe §6.3). The kind
 * decides the questions: pack sizes for goods sold by weight, choices and
 * add-ons for menu items, options for variants, and each kind's own details.
 * The server checks everything again and prices every order itself.
 */
export function OfferingEditor({
  businessId,
  kind,
  offering,
  variants,
}: {
  businessId: string
  kind: Kind
  offering: Offering | null
  variants: Variant[]
}) {
  const router = useRouter()
  const isNew = offering === null
  const [title, setTitle] = useState(offering?.title ?? '')
  const [description, setDescription] = useState(offering?.description ?? '')
  const [status, setStatus] = useState(offering?.status === 'active' ? 'active' : 'draft')
  const defaultPriceType = kind.flow === 'enquiry' ? 'starting_from' : 'fixed'
  const [priceType, setPriceType] = useState(offering?.price_type ?? defaultPriceType)
  const [price, setPrice] = useState(offering?.price_amount != null ? String(offering.price_amount) : '')
  const [taxCode, setTaxCode] = useState(offering?.hsn_sac ?? '')
  const [taxRate, setTaxRate] = useState(offering?.tax_rate != null ? String(offering.tax_rate) : '')
  const [sku, setSku] = useState(offering?.sku ?? '')
  const [barcode, setBarcode] = useState(offering?.barcode ?? '')
  const [attrs, setAttrs] = useState<Attr>(() =>
    Object.fromEntries(kind.fields.map((f) => [f.key, toForm(f, offering?.attributes?.[f.key] ?? (f.key === 'price_per' ? 'kg' : undefined))])),
  )
  const [packs, setPacks] = useState<Pack[]>(offering?.sell_units ?? (kind.packs ? [{ label: '500 g', qty: 500 }, { label: '1 kg', qty: 1000 }] : []))
  const [groups, setGroups] = useState<OptionGroup[]>(offering?.option_groups ?? [])
  const [axes, setAxes] = useState<Axis[]>(offering?.variant_options ?? [])
  const [track, setTrack] = useState(offering?.track_inventory ?? kind.packs)
  const gramStock = kind.packs || offering?.stock_unit === 'g' || offering?.stock_unit === 'ml'
  const [reorder, setReorder] = useState(
    offering?.low_stock_threshold != null ? String(gramStock ? offering.low_stock_threshold / 1000 : offering.low_stock_threshold) : '',
  )
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  const per = String(attrs.price_per || 'kg')
  const combos = axes.reduce((n, a) => n * Math.max(a.values.length, 1), axes.length ? 1 : 0)

  const body = () => {
    const attributes: Record<string, unknown> = {}
    for (const f of kind.fields) {
      const v = attrs[f.key]
      if (v === '' || v === undefined || v === false) continue
      attributes[f.key] = f.type === 'list' ? String(v).split('\n').map((s) => s.trim()).filter(Boolean) : v
    }
    const payload: Record<string, unknown> = {
      title: title.trim(),
      description: description.trim() || null,
      status,
      attributes,
      hsn_sac: taxCode.trim() || null,
      tax_rate: taxRate === '' ? null : Number(taxRate),
    }
    if (kind.flow !== 'give') {
      payload.price_type = kind.packs ? 'fixed' : priceType
      payload.price_amount = price === '' || priceType === 'free' || priceType === 'enquiry' ? null : Number(price)
    }
    if (kind.tax_code === 'HSN') {
      payload.sku = sku.trim() || null
      payload.barcode = barcode.trim() || null
    }
    if (kind.packs) payload.sell_units = packs
    if (kind.options) payload.option_groups = groups
    if (kind.variants) payload.variant_options = axes.filter((a) => a.name.trim() && a.values.length)
    if (kind.stockable) {
      payload.track_inventory = track
      payload.low_stock_threshold = reorder === '' ? null : Math.round(Number(reorder) * (gramStock ? 1000 : 1))
    }
    if (isNew) payload.offering_type = kind.key
    else payload.version = offering?.version
    return payload
  }

  const save = () => {
    setError(null)
    setSaved(null)
    if (!title.trim()) return setError('Give it a name.')
    start(async () => {
      const r = await saveOffering(businessId, offering?.id ?? null, body())
      if (!r.ok) return setError(r.message)
      if (isNew && r.data?.id) {
        router.push(`/b/${businessId}/offerings/${r.data.id}?saved=1`)
      } else {
        setSaved(status === 'active' ? 'Saved. It is live.' : 'Saved as a draft.')
        router.refresh()
      }
    })
  }

  return (
    <div className="bos-works bos-offering">
      <section className="bos-card" aria-labelledby="basics-h">
        <h2 id="basics-h">Basics</h2>
        <div className="bos-form-grid">
          <label>
            <span className="bos-label">Name</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
          </label>
          {kind.tax_code === 'HSN' ? (
            <>
              <label>
                <span className="bos-label">Your code (SKU)</span>
                <input value={sku} onChange={(e) => setSku(e.target.value)} maxLength={64} />
              </label>
              <label>
                <span className="bos-label">Barcode</span>
                <input value={barcode} onChange={(e) => setBarcode(e.target.value)} inputMode="numeric" maxLength={64} />
              </label>
            </>
          ) : null}
        </div>
        <label className="bos-offering__desc">
          <span className="bos-label">Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={5000} />
        </label>
      </section>

      {kind.fields.length ? (
        <section className="bos-card" aria-labelledby="details-h">
          <h2 id="details-h">{kind.label} details</h2>
          <div className="bos-form-grid">
            {kind.fields.map((f) => (
              <FieldInput key={f.key} field={f} value={attrs[f.key]} onChange={(v) => setAttrs((a) => ({ ...a, [f.key]: v }))} />
            ))}
          </div>
        </section>
      ) : null}

      {kind.flow !== 'give' ? (
        <section className="bos-card" aria-labelledby="price-h">
          <h2 id="price-h">Price</h2>
          {!kind.packs ? (
            <fieldset className="bos-choices" style={{ border: 0, padding: 0, margin: '0 0 .8rem' }}>
              <legend className="sr-only">How it is priced</legend>
              {[
                ['fixed', 'Fixed price'],
                ['starting_from', 'Starts from'],
                ['free', 'Free'],
                ['enquiry', 'Ask for price'],
              ].map(([k, label]) => (
                <label key={k} className="bos-choice">
                  <input type="radio" name="price_type" checked={priceType === k} onChange={() => setPriceType(k)} />
                  {label}
                </label>
              ))}
            </fieldset>
          ) : null}
          <div className="bos-form-grid">
            {priceType !== 'free' && priceType !== 'enquiry' ? (
              <label>
                <span className="bos-label">{kind.packs ? `Price per ${per} (₹)` : 'Price (₹)'}</span>
                <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
              </label>
            ) : null}
            <label>
              <span className="bos-label">{kind.tax_code} code</span>
              <input value={taxCode} onChange={(e) => setTaxCode(e.target.value)} inputMode="numeric" maxLength={8}
                placeholder={kind.tax_code === 'HSN' ? '4, 6 or 8 digits' : '6 digits, starts with 99'} />
            </label>
            <label>
              <span className="bos-label">GST rate (%)</span>
              <input inputMode="decimal" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} placeholder="As advised by your CA" />
            </label>
          </div>
        </section>
      ) : null}

      {kind.packs ? (
        <PacksEditor packs={packs} setPacks={setPacks} unit={per === 'litre' ? 'ml' : 'g'} price={price === '' ? null : Number(price)} />
      ) : null}
      {kind.options ? <GroupsEditor groups={groups} setGroups={setGroups} what={kind.key === 'menu_item' ? 'choices and add-ons' : 'choices such as the cut'} /> : null}
      {kind.variants ? (
        <section className="bos-card" aria-labelledby="var-h">
          <h2 id="var-h">Sizes, colours and other options</h2>
          <p className="bos-hint">Add an option and its values. Each combination becomes a variant with its own stock.</p>
          {axes.map((a, i) => (
            <div key={i} className="bos-rowedit">
              <input aria-label="Option name" placeholder="Size" value={a.name}
                onChange={(e) => setAxes((xs) => xs.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
              <input aria-label="Values" placeholder="S, M, L" value={a.values.join(', ')}
                onChange={(e) => setAxes((xs) => xs.map((x, j) => (j === i ? { ...x, values: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } : x)))} />
              <button type="button" className="btn-quiet" onClick={() => setAxes((xs) => xs.filter((_, j) => j !== i))}>Remove</button>
            </div>
          ))}
          {axes.length < 3 ? (
            <button type="button" className="btn-ghost" onClick={() => setAxes((xs) => [...xs, { name: '', values: [] }])}>Add an option</button>
          ) : null}
          {!isNew && offering?.variant_options?.length ? (
            <VariantsPanel businessId={businessId} offeringId={offering.id} variants={variants} combos={combos} />
          ) : null}
        </section>
      ) : null}

      {kind.stockable ? (
        <section className="bos-card" aria-labelledby="stock-h">
          <h2 id="stock-h">Stock</h2>
          <label className="bos-toggle">
            <input type="checkbox" checked={track} onChange={(e) => setTrack(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>Keep count of stock{gramStock ? ` (counted in ${per === 'litre' ? 'millilitres' : 'grams'})` : ''}</span>
          </label>
          {track ? (
            <label style={{ display: 'block', marginTop: '.6rem', maxWidth: 260 }}>
              <span className="bos-label">Tell me when stock falls to{gramStock ? ` (${per === 'litre' ? 'litres' : 'kg'})` : ''}</span>
              <input inputMode="decimal" value={reorder} onChange={(e) => setReorder(e.target.value)} />
            </label>
          ) : null}
        </section>
      ) : null}

      <div className="bos-savebar">
        <label className="bos-toggle">
          <input type="checkbox" checked={status === 'active'} onChange={(e) => setStatus(e.target.checked ? 'active' : 'draft')} />
          <span className="bos-toggle__track" aria-hidden />
          <span>{status === 'active' ? 'Live — shown to customers' : 'Draft — only you can see it'}</span>
        </label>
        <button type="button" onClick={save} disabled={pending}>{pending ? 'Saving…' : isNew ? 'Add' : 'Save'}</button>
        <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">{error ?? saved ?? ''}</p>
      </div>
    </div>
  )
}

function FieldInput({ field: f, value, onChange }: { field: KindField; value: string | boolean | undefined; onChange: (v: string | boolean) => void }) {
  const label = `${f.label}${f.unit ? ` (${f.unit})` : ''}${f.required ? '' : ' — optional'}`
  const id = `f-${f.key}`
  if (f.type === 'bool') {
    return (
      <label className="bos-toggle">
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        <span className="bos-toggle__track" aria-hidden />
        <span>{f.label}</span>
      </label>
    )
  }
  return (
    <label htmlFor={id} className={f.type === 'list' || f.type === 'long_text' ? 'bos-form-wide' : ''}>
      <span className="bos-label">{label}</span>
      {f.type === 'choice' ? (
        <select id={id} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
          <option value="">{f.required ? 'Choose…' : 'Not set'}</option>
          {f.choices.map((c) => <option key={c}>{c}</option>)}
        </select>
      ) : f.type === 'list' || f.type === 'long_text' ? (
        <textarea id={id} rows={3} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input
          id={id}
          type={f.type === 'date' ? 'date' : 'text'}
          inputMode={f.type === 'int' || f.type === 'year' || f.type === 'money' ? 'numeric' : undefined}
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {f.help ? <small className="bos-fieldhelp">{f.help}</small> : null}
    </label>
  )
}

function PacksEditor({ packs, setPacks, unit, price }: { packs: Pack[]; setPacks: (p: Pack[]) => void; unit: string; price: number | null }) {
  const quick = unit === 'ml' ? [[250, '250 ml'], [500, '500 ml'], [1000, '1 litre']] : [[250, '250 g'], [500, '500 g'], [1000, '1 kg']]
  return (
    <section className="bos-card" aria-labelledby="packs-h">
      <h2 id="packs-h">Pack sizes</h2>
      <p className="bos-hint">Customers pick a pack; the price follows from your price per {unit === 'ml' ? 'litre' : 'kg'}.</p>
      {packs.map((p, i) => (
        <div key={i} className="bos-rowedit">
          <input aria-label="Pack name" value={p.label} onChange={(e) => setPacks(packs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
          <label className="bos-rowedit__unit">
            <input aria-label={`Weight in ${unit}`} inputMode="numeric" value={String(p.qty)}
              onChange={(e) => setPacks(packs.map((x, j) => (j === i ? { ...x, qty: Number(e.target.value.replace(/\D/g, '')) || 0 } : x)))} />
            <span>{unit}</span>
          </label>
          <span className="bos-rowedit__price">{price !== null ? inr(Math.round(price * p.qty / 10) / 100) : ''}</span>
          <button type="button" className="btn-quiet" onClick={() => setPacks(packs.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <div className="bos-choices" style={{ marginTop: '.5rem' }}>
        {quick.filter(([, l]) => !packs.some((p) => p.label === l)).map(([q, l]) => (
          <button key={String(l)} type="button" className="btn-ghost" onClick={() => setPacks([...packs, { label: String(l), qty: Number(q) }])}>+ {l}</button>
        ))}
        <button type="button" className="btn-ghost" onClick={() => setPacks([...packs, { label: '', qty: 0 }])}>+ Other size</button>
      </div>
    </section>
  )
}

function GroupsEditor({ groups, setGroups, what }: { groups: OptionGroup[]; setGroups: (g: OptionGroup[]) => void; what: string }) {
  const update = (i: number, g: Partial<OptionGroup>) => setGroups(groups.map((x, j) => (j === i ? { ...x, ...g } : x)))
  return (
    <section className="bos-card" aria-labelledby="groups-h">
      <h2 id="groups-h">Choices</h2>
      <p className="bos-hint">Add {what}. A choice can add to the price.</p>
      {groups.map((g, i) => (
        <fieldset key={i} className="bos-group">
          <legend className="sr-only">Choice group {i + 1}</legend>
          <div className="bos-rowedit">
            <input aria-label="Group name" placeholder="Size, Cut, Add-ons…" value={g.name} onChange={(e) => update(i, { name: e.target.value })} />
            <label className="bos-toggle">
              <input type="checkbox" checked={g.required} onChange={(e) => update(i, { required: e.target.checked })} />
              <span className="bos-toggle__track" aria-hidden />
              <span>Must choose</span>
            </label>
            <label className="bos-rowedit__unit">
              <span>Up to</span>
              <input aria-label="How many can be picked" inputMode="numeric" value={String(g.max)}
                onChange={(e) => update(i, { max: Math.max(1, Number(e.target.value.replace(/\D/g, '')) || 1) })} />
            </label>
            <button type="button" className="btn-quiet" onClick={() => setGroups(groups.filter((_, j) => j !== i))}>Remove group</button>
          </div>
          {g.choices.map((c, ci) => (
            <div key={ci} className="bos-rowedit bos-rowedit--choice">
              <input aria-label="Choice" value={c.label}
                onChange={(e) => update(i, { choices: g.choices.map((x, j) => (j === ci ? { ...x, label: e.target.value } : x)) })} />
              <label className="bos-rowedit__unit">
                <span>+ ₹</span>
                <input aria-label="Adds to price" inputMode="decimal" value={String(c.price_delta)}
                  onChange={(e) => update(i, { choices: g.choices.map((x, j) => (j === ci ? { ...x, price_delta: e.target.value } : x)) })} />
              </label>
              <button type="button" className="btn-quiet" onClick={() => update(i, { choices: g.choices.filter((_, j) => j !== ci) })}>Remove</button>
            </div>
          ))}
          <button type="button" className="btn-quiet" onClick={() => update(i, { choices: [...g.choices, { label: '', price_delta: 0 }] })}>+ Add a choice</button>
        </fieldset>
      ))}
      <button type="button" className="btn-ghost" onClick={() => setGroups([...groups, { name: '', required: false, max: 1, choices: [{ label: '', price_delta: 0 }] }])}>
        Add a group of choices
      </button>
    </section>
  )
}

function VariantsPanel({ businessId, offeringId, variants, combos }: { businessId: string; offeringId: string; variants: Variant[]; combos: number }) {
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<string | null>(null)
  const missing = Math.max(combos - variants.length, 0)
  return (
    <div className="bos-variants">
      <p className="bos-hint">
        {variants.length} variant{variants.length === 1 ? '' : 's'} of {combos} combinations.
      </p>
      {variants.length ? (
        <ul className="bos-pills">{variants.map((v) => <li key={v.id} className="bos-pill">{v.name}</li>)}</ul>
      ) : null}
      {missing > 0 ? (
        <button type="button" disabled={pending} onClick={() => start(async () => {
          const r = await makeVariants(businessId, offeringId)
          setMsg(r.ok ? 'Variants made. Set stock for each on the Stock page.' : r.message)
        })}>
          {pending ? 'Making…' : `Make the ${missing} missing variant${missing === 1 ? '' : 's'}`}
        </button>
      ) : null}
      {msg ? <p className="bos-status" role="status">{msg}</p> : null}
    </div>
  )
}
