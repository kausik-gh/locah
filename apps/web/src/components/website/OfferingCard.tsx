'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { addToBasket } from '@/lib/checkout-api'
import { Specs, money, priceLabel, type OptionGroup, type PublicOffering } from './offering-view'

export type { PublicOffering } from './offering-view'

/**
 * One offering on a business's website, shown the way its kind is transacted
 * (Capability Universe §6.3): goods by weight pick a pack and cut, menu items
 * their choices and add-ons, products their size and colour, causes an amount,
 * and homes, vehicles and past work open an enquiry. Every price shown comes
 * from the business's catalogue via the API; checkout prices it again.
 */

export function OfferingCard({
  o,
  slug,
  canOrder,
  canBook,
  canEnquire,
  onAdded,
}: {
  o: PublicOffering
  slug: string
  canOrder: boolean
  canBook: boolean
  canEnquire: boolean
  onAdded?: (count: number) => void
}) {
  const flow = o.kind?.flow ?? 'cart'
  const groups = useMemo(() => o.option_groups ?? [], [o.option_groups])
  const [pack, setPack] = useState(o.packs?.[0]?.label ?? '')
  const [variant, setVariant] = useState(o.variants?.[0]?.id ?? '')
  const [picked, setPicked] = useState<Record<string, string[]>>(() =>
    Object.fromEntries(groups.filter((g) => !g.text && g.required && g.max === 1).map((g) => [g.name, [g.choices[0].label]])),
  )
  const [notes, setNotes] = useState<Record<string, string>>({})
  const suggested = ((o.attributes?.suggested_amounts as string[] | undefined) ?? []).map(Number).filter(Boolean)
  const minGift = Number(o.attributes?.min_amount ?? 1)
  const [gift, setGift] = useState<string>(String(suggested[0] ?? minGift))
  const [added, setAdded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const chooses = flow === 'cart' && (o.packs?.length || groups.length || (o.variants?.length ?? 0) > 0)
  const unitPrice = useMemo(() => {
    let base = o.price_amount ?? 0
    if (o.packs?.length) base = o.packs.find((p) => p.label === pack)?.price_amount ?? base
    const v = o.variants?.find((x) => x.id === variant)
    if (v && v.price_amount !== null) base = v.price_amount
    for (const g of groups) for (const label of picked[g.name] ?? []) {
      base += Number(g.choices.find((c) => c.label === label)?.price_delta ?? 0)
    }
    return base
  }, [o, pack, variant, picked, groups])

  const toggle = (g: OptionGroup, label: string) =>
    setPicked((p) => {
      const cur = p[g.name] ?? []
      if (g.max === 1) return { ...p, [g.name]: cur[0] === label && !g.required ? [] : [label] }
      if (cur.includes(label)) return { ...p, [g.name]: cur.filter((x) => x !== label) }
      return cur.length >= g.max ? p : { ...p, [g.name]: [...cur, label] }
    })

  const add = () => {
    setError(null)
    const missing = groups.find((g) => !g.text && g.required && !(picked[g.name] ?? []).length)
    if (missing) return setError(`Choose ${missing.name.toLowerCase()}`)
    const unwritten = groups.find((g) => g.text && g.required && !(notes[g.name] ?? '').trim())
    if (unwritten) return setError(`Write the ${unwritten.name.toLowerCase()}`)
    const options: Record<string, unknown> = {}
    const words: string[] = []
    if (pack) { options.pack = pack; words.push(pack) }
    const choices = Object.fromEntries(Object.entries(picked).filter(([, v]) => v.length))
    if (Object.keys(choices).length) { options.choices = choices; words.push(Object.values(choices).flat().join(', ')) }
    const written = Object.fromEntries(Object.entries(notes).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v))
    if (Object.keys(written).length) { options.notes = written; words.push(...Object.values(written).map((v) => `“${v}”`)) }
    const v = o.variants?.find((x) => x.id === variant)
    if (v) words.unshift(v.name)
    const count = addToBasket(slug, {
      offering_id: o.id, title: o.title, quantity: 1, unit_price: unitPrice, currency: o.currency || 'INR',
      options: Object.keys(options).length ? options : undefined, variant_id: v?.id, detail: words.join(' · ') || undefined,
    })
    setAdded(`Added${words.length ? ` — ${words.join(' · ')}` : ''}`)
    onAdded?.(count)
  }

  const give = () => {
    setError(null)
    const amount = Number(gift)
    if (!amount || amount < minGift) return setError(`Gifts start at ${money(minGift, o.currency)}`)
    const count = addToBasket(slug, {
      offering_id: o.id, title: o.title, quantity: 1, unit_price: amount, currency: o.currency || 'INR',
      options: { amount }, detail: `Gift of ${money(amount, o.currency)}`,
    })
    setAdded(`Gift of ${money(amount, o.currency)} added`)
    onAdded?.(count)
  }

  const goal = Number(o.attributes?.goal_amount ?? 0)
  const raised = o.raised_amount ?? 0
  const enquire = (purpose: string, label: string, primary: boolean) => (
    <Link key={purpose} className={`ls-btn${primary ? '' : ' ls-btn--outline'}`}
      href={`/${slug}/enquire?offering_id=${o.id}&purpose=${purpose}`}>{label}</Link>
  )
  const extraPurpose = (label: string) => (label.includes('site visit') ? 'site_visit' : label.includes('test drive') ? 'test_drive' : 'enquiry')

  return (
    <article className="ls-item ls-offer">
      {o.image_url ? (
        <div className="ls-item__media">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={o.image_url} alt="" loading="lazy" />
        </div>
      ) : null}
      <div className="ls-item__body">
        {o.kind && flow !== 'cart' ? <p className="ls-offer__kind">{o.kind.label}</p> : null}
        <h3 className="ls-item__title">{o.title}</h3>
        {o.description ? <p className="ls-item__desc">{o.description}</p> : null}
        <Specs o={o} />
        {o.preorder && canOrder ? (
          <p className="ls-offer__ahead">
            {o.preorder.needed ? 'Made to order' : 'Order ahead'}
            {o.preorder.earliest_words ? ` · ready from ${o.preorder.earliest_words}` : ''}
            {o.preorder.advance ? ` · ${o.preorder.advance.type === 'percent' ? `${o.preorder.advance.value}%` : money(o.preorder.advance.value, o.currency)} advance` : ''}
          </p>
        ) : null}
        {flow === 'give' ? (
          <div className="ls-gift">
            {goal > 0 ? (
              <div className="ls-gift__progress" role="progressbar" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={Math.min(raised, goal)}
                aria-label={`${money(raised, o.currency)} given of ${money(goal, o.currency)}`}>
                <span style={{ width: `${Math.min(100, (raised * 100) / goal)}%` }} />
              </div>
            ) : null}
            {goal > 0 ? <p className="ls-meta">{money(raised, o.currency)} given of {money(goal, o.currency)}</p> : null}
            {canOrder ? (
              <>
                <div className="ls-choice" role="group" aria-label="Amount">
                  {suggested.map((a) => (
                    <button key={a} type="button" className={`ls-chip${Number(gift) === a ? ' is-on' : ''}`} onClick={() => setGift(String(a))}>
                      {money(a, o.currency)}
                    </button>
                  ))}
                  <label className="ls-gift__other">
                    <span>Other</span>
                    <input inputMode="numeric" value={gift} onChange={(e) => setGift(e.target.value.replace(/[^\d]/g, ''))} aria-label="Amount to give" />
                  </label>
                </div>
                <div className="ls-item__foot"><span /><button type="button" className="ls-btn" onClick={give}>{o.kind?.cta ?? 'Give'}</button></div>
              </>
            ) : null}
          </div>
        ) : chooses && canOrder ? (
          <div className="ls-chooser">
            {o.packs?.length ? (
              <div className="ls-choice" role="radiogroup" aria-label="Pack size">
                {o.packs.map((p) => (
                  <button key={p.label} type="button" role="radio" aria-checked={pack === p.label}
                    className={`ls-chip${pack === p.label ? ' is-on' : ''}`} onClick={() => setPack(p.label)}>
                    {p.label}{p.price_amount !== null ? ` · ${money(p.price_amount, o.currency)}` : ''}
                  </button>
                ))}
              </div>
            ) : null}
            {o.variants && o.variants.length > 0 ? (
              <label className="ls-chooser__select">
                <span>Option</span>
                <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                  {o.variants.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </label>
            ) : null}
            {groups.map((g) => g.text ? (
              <label key={g.name} className="ls-chooser__text">
                <span>{g.name}{g.required ? '' : ' (optional)'}</span>
                <input value={notes[g.name] ?? ''} maxLength={g.max_length ?? 40}
                  onChange={(e) => setNotes((n) => ({ ...n, [g.name]: e.target.value }))} />
              </label>
            ) : (
              <div key={g.name} className="ls-choice" role="group" aria-label={g.name}>
                <span className="ls-choice__name">{g.name}{g.max > 1 ? ` (up to ${g.max})` : ''}</span>
                {g.choices.map((c) => {
                  const on = (picked[g.name] ?? []).includes(c.label)
                  return (
                    <button key={c.label} type="button" aria-pressed={on} className={`ls-chip${on ? ' is-on' : ''}`} onClick={() => toggle(g, c.label)}>
                      {c.label}{Number(c.price_delta) > 0 ? ` +${money(Number(c.price_delta), o.currency)}` : ''}
                    </button>
                  )
                })}
              </div>
            ))}
            <div className="ls-item__foot">
              <span className="ls-price">{money(unitPrice, o.currency)}</span>
              <button type="button" className="ls-btn" onClick={add}>{o.kind?.cta ?? 'Add'}</button>
            </div>
          </div>
        ) : (
          <div className="ls-item__foot">
            {priceLabel(o) ? <span className="ls-price">{priceLabel(o)}</span> : <span />}
            <span className="ls-offer__actions">
              {flow === 'cart' && canOrder ? <button type="button" className="ls-btn" onClick={add}>{o.kind?.cta ?? 'Add'}</button> : null}
              {flow === 'booking' && canBook ? <Link className="ls-btn" href={`/${slug}/book?offering_id=${o.id}`}>{o.kind?.cta ?? 'Book'}</Link> : null}
              {(flow === 'enquiry' || flow === 'membership') && canEnquire ? (
                <>
                  {(o.kind?.extra_ctas ?? []).map((label) => enquire(extraPurpose(label.toLowerCase()), label, true))}
                  {enquire('enquiry', flow === 'membership' ? 'Join' : o.kind?.cta ?? 'Enquire', (o.kind?.extra_ctas ?? []).length === 0)}
                </>
              ) : null}
            </span>
          </div>
        )}
        {added ? <p className="ls-offer__added" role="status">{added} · <Link href={`/${slug}/checkout`}>View basket</Link></p> : null}
        {error ? <p className="ls-offer__error" role="alert">{error}</p> : null}
      </div>
    </article>
  )
}
