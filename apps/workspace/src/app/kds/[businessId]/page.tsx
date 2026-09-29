import Link from 'next/link'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { KdsBoard, type Board } from './KdsBoard'
import '../kds.css'

export const dynamic = 'force-dynamic'

/**
 * Kitchen display (Capability Universe §7.1). Full screen, outside the
 * Workspace shell. Prices and phone numbers are not on this surface.
 */
export default async function KdsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = params.businessId
  const [board, business] = await Promise.all([
    apiTry<{ data: Board }>(`/v1/platform/businesses/${businessId}/kitchen/board`, token),
    apiTry<{ data: { display_name: string } }>(`/v1/b/${businessId}`, token),
  ])
  if (!board.ok) {
    const why = board.error.code === 'PERMISSION_DENIED'
      ? 'Your role does not include the kitchen pass. Ask the owner for the Kitchen role.'
      : board.error.code === 'MODULE_NOT_ACTIVE'
        ? 'Kitchen display is not switched on yet (Modules and integrations).'
        : board.error.message
    return (
      <main className="kds-blocked">
        <h1>The kitchen pass is not available</h1>
        <p>{why}</p>
        <Link className="btn" href={`/b/${businessId}`}>Back to the Workspace</Link>
      </main>
    )
  }
  return (
    <KdsBoard
      businessId={businessId}
      businessName={business.ok ? business.data.data.display_name : ''}
      apiUrl={platformUrl('api')}
      initialToken={token}
      initial={board.data.data}
    />
  )
}
