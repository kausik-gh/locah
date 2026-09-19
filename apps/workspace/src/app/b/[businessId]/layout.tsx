import { notFound, redirect } from 'next/navigation'
import { ReactNode } from 'react'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { AppSidebar, type NavBusiness } from '@/components/AppSidebar'

export const dynamic = 'force-dynamic'

type Context = {
  module_states: Record<string, string>
}

/**
 * Business workspace shell. Fetches only what the sidebar needs — the business
 * list for the switcher, module states for the module-aware nav, and the
 * unread count — in one parallel round. No page logic here.
 */
export default async function WorkspaceBusinessLayout({
  children,
  params,
}: {
  children: ReactNode
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    // Carry the business through the sign-in hand-off. Without it, someone
    // whose session expired mid-task signs in and lands on the Workspace root,
    // having to re-find the business they were already in.
    redirect(`/login?destination=${encodeURIComponent(`/b/${params.businessId}`)}`)
  }

  const bh = businessHeaders(params.businessId)
  const [businessesRes, contextRes, unreadRes] = await Promise.all([
    apiTry<{ data: NavBusiness[] }>('/v1/platform/businesses', token),
    apiTry<{ data: Context }>('/v1/me/context', token, bh),
    apiTry<{ data: { unread_count: number } }>(
      `/v1/platform/businesses/${params.businessId}/notifications/unread-count`,
      token
    ),
  ])

  const businesses = businessesRes.ok ? businessesRes.data.data : []

  // Someone with a good session but no membership of THIS business used to get
  // the full Workspace shell — real headings, empty tables — for a business
  // that is not theirs. No data leaked (every endpoint refuses separately), but
  // the page confirmed the id exists and read as a broken Workspace rather than
  // a refusal. `notFound` is the honest answer and reveals nothing.
  //
  // The list is the server's own answer to "which businesses is this identity an
  // active member of", so this is a rendering consequence of server-side
  // authorization, not a second opinion about it. It is deliberately skipped
  // when the list could not be loaded: an API outage must not lock an owner out
  // of their own Workspace.
  if (businessesRes.ok && !businesses.some((b) => b.id === params.businessId)) {
    notFound()
  }
  const moduleStates = contextRes.ok ? contextRes.data.data.module_states ?? {} : {}
  const unreadCount = unreadRes.ok ? unreadRes.data.data.unread_count : 0

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-background)' }}>
      <AppSidebar
        businessId={params.businessId}
        businesses={businesses}
        moduleStates={moduleStates}
        unreadCount={unreadCount}
      />
      <main className="ws-page" style={{ flex: 1, minWidth: 0 }}>
        {children}
      </main>
    </div>
  )
}
