import Link from 'next/link'
import { redirect } from 'next/navigation'
import { businessSiteUrl, platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { PosApp, type PosSetup } from './PosApp'
import '../pos.css'

export const dynamic = 'force-dynamic'

/**
 * The counter (Capability Universe §7.3 surface "POS: tablet or desktop, full
 * screen, cashier"; §14.1–§14.3). Full screen, outside the Workspace shell. It
 * talks to the API directly and keeps working when the connection drops.
 */
export default async function PosPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [setup, business] = await Promise.all([
    apiTry<{ data: PosSetup }>(`/v1/platform/businesses/${b}/pos/setup`, token),
    apiTry<{ data: { display_name: string; slug: string } }>(`/v1/b/${b}`, token),
  ])
  if (!setup.ok) {
    const why = setup.error.code === 'PERMISSION_DENIED'
      ? 'Your role does not include counter billing. Ask the owner to give you the Cashier role.'
      : setup.error.code === 'MODULE_NOT_ACTIVE'
        ? 'Counter billing is not switched on for this business yet (Modules & integrations → Counter billing).'
        : setup.error.message
    return (
      <main className="pos-blocked">
        <h1>The counter is not available</h1>
        <p>{why}</p>
        <Link className="btn" href={`/b/${b}`}>Back to the Workspace</Link>
      </main>
    )
  }
  const slug = business.ok ? business.data.data.slug : ''
  return (
    <PosApp
      businessId={b}
      businessName={business.ok ? business.data.data.display_name : ''}
      initialToken={token}
      apiUrl={platformUrl('api')}
      billBase={slug ? businessSiteUrl(slug, '/bill/') : ''}
      setup={setup.data.data}
    />
  )
}
