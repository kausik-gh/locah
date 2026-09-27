'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { giveInStoreCode } from '../../settings/counter/counter-actions'

/**
 * Barcode and labels for the counter (Capability Universe §14.3): packaged
 * goods keep their printed barcode; loose goods get an in-store code, printed
 * on an A4 sheet or a label printer.
 */
export function LabelTools({ businessId, offeringId, barcode }: { businessId: string; offeringId: string; barcode: string | null }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [code, setCode] = useState(barcode)
  const [copies, setCopies] = useState('1')
  const [msg, setMsg] = useState<string | null>(null)
  const printable = Boolean(code && /^\d{13}$/.test(code))
  return (
    <section className="bos-card" aria-labelledby="label-h" style={{ maxWidth: 860, marginTop: '1rem' }}>
      <h2 id="label-h">Barcode and labels</h2>
      {code ? <p className="bos-hint">Barcode <code>{code}</code> — scan it at the counter.</p> : (
        <p className="bos-hint">No barcode yet. Loose goods can get an in-store code to print on labels.</p>
      )}
      <div className="bos-inv-buttons">
        {!code ? (
          <button type="button" disabled={pending} onClick={() => start(async () => {
            const r = await giveInStoreCode(businessId, offeringId)
            if (!r.ok || !r.data) return setMsg(r.ok ? 'No code came back' : r.message)
            setCode(r.data.barcode)
            setMsg('In-store code given')
            router.refresh()
          })}>Give an in-store code</button>
        ) : null}
        {printable ? (
          <>
            <label className="bos-rowedit__unit">Copies <input inputMode="numeric" value={copies} onChange={(e) => setCopies(e.target.value.replace(/\D/g, '').slice(0, 2))} /></label>
            <a className="btn btn-ghost" target="_blank" rel="noreferrer" href={`/b/${businessId}/pos/labels?ids=${offeringId}&copies=${copies || 1}`}>Print on A4 sheet</a>
            <a className="btn btn-ghost" target="_blank" rel="noreferrer" href={`/b/${businessId}/pos/labels?ids=${offeringId}&copies=${copies || 1}&layout=label_50x25`}>Label printer (50 × 25 mm)</a>
          </>
        ) : null}
        {msg ? <p className="bos-status" role="status">{msg}</p> : null}
      </div>
    </section>
  )
}
