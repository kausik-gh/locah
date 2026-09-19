import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

/**
 * Hand a visitor over to Workspace, which lives on another origin.
 *
 * Sign-in happens once, on the public app, for every surface — so Workspace has
 * to be able to say "send them back to me afterwards". It cannot do that with a
 * destination of `https://app.<domain>/…`: `resolveDestinationIntent` rejects
 * absolute URLs, and rightly, because accepting them is an open redirect.
 *
 * `/workspace/...` is the relative form it can use. The origin is supplied here
 * from deployment configuration and never from the request, so the only thing
 * the caller controls is the path within Workspace.
 */
export default function WorkspaceHandoff({ params }: { params: { path?: string[] } }) {
  const segments = (params.path ?? [])
    // A segment is one path component; anything that could re-open the origin
    // (a scheme, a second slash, a traversal) is not one.
    .filter((s) => s && s !== '.' && s !== '..' && !s.includes('/') && !s.includes('\\'))
    .map((s) => encodeURIComponent(s))

  redirect(platformUrl('workspace', segments.length ? `/${segments.join('/')}` : '/'))
}
