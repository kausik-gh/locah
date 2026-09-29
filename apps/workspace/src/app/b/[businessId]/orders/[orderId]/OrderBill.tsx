'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { billOrder } from '../../invoices/invoice-actions'
import { useWsWords } from '@/components/WsWords'

type Live = { id: string; number: string | null; kind_label: string; status: string } | null

/** The order's bill (Capability Universe §14: every order gets its bill from the one billing engine). */
export function OrderBill({ businessId, orderId, live, cancelled }: { businessId: string; orderId: string; live: Live; cancelled: boolean }) {
  const t = useWsWords()
  const router = useRouter()
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  if (live) {
    return (
      <p className="bos-inv-orderbill">
        <span>{t(live.kind_label)} <strong>{live.number}</strong></span>
        <Link className="btn btn-ghost" href={`/b/${businessId}/invoices/${live.id}`}>{t('Open bill')}</Link>
      </p>
    )
  }
  if (cancelled) return <p className="bos-hint">{t('Cancelled orders are not billed.')}</p>
  return (
    <div className="bos-inv-orderbill">
      <span>{t('Not billed yet.')}</span>
      <button type="button" disabled={pending} onClick={() => start(async () => {
        setError(null)
        const r = await billOrder(businessId, orderId, {})
        if (!r.ok || !r.data) return setError(r.ok ? t('Nothing came back') : r.message)
        router.push(`/b/${businessId}/invoices/${r.data.id}`)
      })}>{pending ? t('Issuing…') : t('Issue bill')}</button>
      {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
    </div>
  )
}
