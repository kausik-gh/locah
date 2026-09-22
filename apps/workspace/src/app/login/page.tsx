import { redirect } from 'next/navigation'
import { platformUrl, resolvePlatformOrigins } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { WorkspaceLoginForm } from './WorkspaceLoginForm'

export const dynamic = 'force-dynamic'

/**
 * Workspace auth uses the shared Platform Identity ceremony on apps/web.
 *
 * The hand-off carries where the person was going. Without it they sign in and
 * land on the public home page, having to find their way back into Workspace by
 * hand — which reads as a failed sign-in even though it succeeded.
 */
export default async function WorkspaceLoginRedirect({
  searchParams,
}: {
  searchParams: { destination?: string | string[] }
}) {
  const raw = Array.isArray(searchParams.destination)
    ? searchParams.destination[0]
    : searchParams.destination

  const destination =
    raw && raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/login')
      ? raw
      : '/'
  const origins = resolvePlatformOrigins()
  // Separate railway.app hosts cannot share a cookie. Let this host establish
  // its own Supabase session; a shared-domain deployment still uses the single
  // public sign-in ceremony below.
  const sameHost = new URL(origins.web).hostname === new URL(origins.workspace).hostname
  if (!origins.sessionCookieDomain && !sameHost) {
    if (await getAccessToken()) redirect(destination)
    return <WorkspaceLoginForm destination={destination} />
  }

  // `/workspace/...` is the relative form apps/web accepts and resolves back to
  // this origin; a Workspace path is turned into it rather than sent as-is.
  const intent =
    destination !== '/'
      ? `/workspace${destination}`
      : '/workspace'

  redirect(`${platformUrl('web', '/login')}?destination=${encodeURIComponent(intent)}`)
}
