import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import type { CatalogueItem } from '../ItemPicker'
import { PhoneOrder } from './PhoneOrder'
import { pageWords } from '@/lib/ws-lang'

export const dynamic = 'force-dynamic'

type Offering = CatalogueItem & { offering_type: string; status: string }

/** Take a phone order (FR-OR-13): the same order as the website, entered by staff. */
export default async function NewPhoneOrderPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const t = pageWords()
  const b = `/v1/platform/businesses/${params.businessId}`
  const [products, kinds, settings] = await Promise.all([
    apiTry<{ data: Offering[] }>(`${b}/products?status=active`, token),
    apiTry<{ data: { key: string; flow: string }[] }>('/v1/public/offering-kinds', token),
    apiTry<{ data: { active_modes: string[] } }>(`/v1/b/${params.businessId}/fulfilment/settings`, token),
  ])
  const back = <Link href={`/b/${params.businessId}/orders`}>{t('Orders')}</Link>
  const header = <PageHeader title={t('Take a phone order')} breadcrumb={back}
    subtitle={t('Priced and placed exactly like an order on your website — it joins your Orders as a phone order.')} />
  if (!products.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={products.error} businessId={params.businessId} moduleLabel={t('Orders')} />
      </div>
    )
  }
  const cart = new Set((kinds.ok ? kinds.data.data : []).filter((k) => k.flow === 'cart').map((k) => k.key))
  const items = products.data.data.filter((o) => o.status === 'active' && o.title !== 'Delivery fee' && (cart.size === 0 || cart.has(o.offering_type)))
  const modes = settings.ok && settings.data.data.active_modes.length ? settings.data.data.active_modes.filter((m) => m === 'pickup' || m === 'delivery') : ['pickup']
  return (
    <div className="bos-page">
      {header}
      <PhoneOrder businessId={params.businessId} items={items} modes={modes.length ? modes : ['pickup']} />
    </div>
  )
}
