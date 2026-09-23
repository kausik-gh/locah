'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { BusinessInterviewData, CatalogueEdit } from '@platform/contracts'
import { interviewAction } from '../interview/actions'

const NEED_LABEL: Record<string, string> = {
  varieties: 'varieties',
  cuts: 'cuts',
  sizes: 'sizes',
  price: 'price',
  photo: 'photo',
}

/**
 * What Locah understood about the range, and what it still needs — completed
 * in place. Prices and varieties typed here go into the same catalogue the
 * conversation builds, and appear on the draft site at once. Creating draft
 * catalogue items stays a separate, explicit approval.
 */
export function SetupOfferings({ data }: { data: BusinessInterviewData }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [edits, setEdits] = useState<Record<string, { price: string; unit: string; add: string }>>(
    {}
  )
  const bp = data.blueprint
  const lines = data.understanding?.catalogue ?? []
  const approved = bp.approved_modules.includes('offerings-catalog')
  if (bp.completion_state.status !== 'built' || lines.length === 0) return null

  const groups = bp.taxonomy?.groups ?? []
  const applied = new Set(bp.applied_setup_offerings.map((name) => name.toLocaleLowerCase()))
  const waiting = groups.reduce((sum, g) => sum + Math.max(g.items.length, 1), 0) - applied.size

  async function send(change: { action: 'setup' | 'catalogue'; catalogue?: CatalogueEdit[] }) {
    setBusy(true)
    setError('')
    try {
      const result = await interviewAction(bp.business_id, {
        ...change,
        revision: bp.revision,
        request_id: crypto.randomUUID(),
      })
      if (!result.ok) {
        setError(result.error)
        if (result.stale) router.refresh()
        return
      }
      setOpen(false)
      setEdits({})
      router.refresh()
    } catch {
      setError('Could not save that. Nothing was published; please try again.')
    } finally {
      setBusy(false)
    }
  }

  function save() {
    const catalogue: CatalogueEdit[] = Object.entries(edits)
      .map(([group, v]) => ({
        group,
        price: v.price.trim(),
        unit: v.unit.trim(),
        add_items: v.add
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      }))
      .filter((e) => e.price || e.add_items.length)
    if (catalogue.length) void send({ action: 'catalogue', catalogue })
  }

  return (
    <section className="lp-setup" aria-label="Your catalogue">
      <h2>What I understood you sell</h2>
      <p>
        This shapes your website. Fill in what is missing whenever you are ready — nothing is
        invented.
      </p>
      <ul>
        {lines.map((line) => (
          <li key={line.name}>
            <strong>
              {line.name}
              {line.suggested_label ? <em> · grouped by Locah</em> : null}
            </strong>
            {line.items.length ? <span>{line.items.join(' · ')}</span> : null}
            <span>{[line.sold_by, line.price].filter(Boolean).join(' · ') || 'Price not set'}</span>
            {line.needs.length ? (
              <span className="lp-setup__needs">
                Need: {line.needs.map((n) => NEED_LABEL[n] || n).join(' · ')}
              </span>
            ) : (
              <span className="lp-setup__needs lp-setup__needs--done">Complete</span>
            )}
          </li>
        ))}
      </ul>

      {open ? (
        <div className="lp-setup__form">
          {lines.map((line) => {
            const byWeight = /kg|weight/i.test(line.sold_by)
            const value = edits[line.name] ?? { price: '', unit: byWeight ? 'per kg' : '', add: '' }
            const set = (patch: Partial<typeof value>) =>
              setEdits((all) => ({ ...all, [line.name]: { ...value, ...patch } }))
            const wantsItems = line.needs.some(
              (n) => n === 'varieties' || n === 'cuts' || n === 'sizes'
            )
            return (
              <fieldset key={line.name} disabled={busy}>
                <legend>{line.name}</legend>
                <label>
                  Price
                  <input
                    inputMode="decimal"
                    placeholder="₹ 240"
                    value={value.price}
                    onChange={(e) => set({ price: e.target.value })}
                  />
                </label>
                <label>
                  Per
                  <input
                    placeholder="per kg"
                    value={value.unit}
                    onChange={(e) => set({ unit: e.target.value })}
                  />
                </label>
                {wantsItems ? (
                  <label className="lp-setup__wide">
                    {line.needs.includes('cuts') ? 'Cuts' : 'Varieties'} (comma separated)
                    <input
                      placeholder="Seer fish, Pomfret, Sardine"
                      value={value.add}
                      onChange={(e) => set({ add: e.target.value })}
                    />
                  </label>
                ) : null}
              </fieldset>
            )
          })}
          <div className="lp-setup__actions">
            <button type="button" className="lc-btn lc-btn--primary" disabled={busy} onClick={save}>
              {busy ? 'Saving…' : 'Save to my catalogue'}
            </button>
            <button
              type="button"
              className="lc-btn lc-btn--ghost"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="lp-setup__actions">
          <button
            type="button"
            className="lc-btn lc-btn--ghost"
            disabled={busy}
            onClick={() => setOpen(true)}
          >
            Complete catalogue
          </button>
          {approved && waiting > 0 ? (
            <button
              type="button"
              className="lc-btn lc-btn--primary"
              disabled={busy}
              onClick={() => void send({ action: 'setup' })}
            >
              {busy ? 'Creating drafts…' : 'Create draft catalogue items'}
            </button>
          ) : null}
        </div>
      )}
      <p className="lp-setup__note">
        Draft items stay private until you complete and publish them. Prices only appear where you
        gave them.
      </p>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  )
}
