import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

/**
 * Workspace auth uses the shared Platform Identity ceremony on apps/web.
 *
 * The hand-off carries where the person was going. Without it they sign in and
 * land on the public home page, having to find their way back into Workspace by
 * hand — which reads as a failed sign-in even though it succeeded.
 */
export default function WorkspaceLoginRedirect({
  searchParams,
}: {
  searchParams: { destination?: string | string[] }
}) {
  const raw = Array.isArray(searchParams.destination)
    ? searchParams.destination[0]
    : searchParams.destination

  // `/workspace/...` is the relative form apps/web accepts and resolves back to
  // this origin; a Workspace path is turned into it rather than sent as-is.
  const intent =
    raw && raw.startsWith('/') && !raw.startsWith('//')
      ? `/workspace${raw === '/' ? '' : raw}`
      : '/workspace'

  redirect(`${platformUrl('web', '/login')}?destination=${encodeURIComponent(intent)}`)
}
