import Link from 'next/link'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { JoinPanel, type JoinView } from './JoinPanel'

export const dynamic = 'force-dynamic'

export const metadata = { robots: { index: false, follow: false } }

function emailFromToken(token: string | null): string | null {
  if (!token) return null
  try {
    const part = token.split('.')[1]
    const json = JSON.parse(Buffer.from(part.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
    return typeof json.email === 'string' ? json.email : null
  } catch {
    return null
  }
}

/**
 * The page a new team member opens from the link the owner shared. It says
 * who added them and as what, then lets them create their login (or sign in)
 * and join. Only the invited email can join.
 */
export default async function JoinPage({ params }: { params: { token: string } }) {
  const res = await fetch(platformUrl('api', `/v1/public/join/${encodeURIComponent(params.token)}`), {
    cache: 'no-store',
  })
  const view: JoinView | null = res.ok ? ((await res.json()).data as JoinView) : null
  const access = await getAccessToken()
  return (
    <main className="bos-join">
      <p className="bos-join__brand">LOCAH Workspace</p>
      {!view ? (
        <section className="bos-card">
          <h1>This link does not work</h1>
          <p className="bos-hint">
            It may have been used already, replaced by a newer link, or withdrawn. Ask the person who added you
            for a new one.
          </p>
          <Link href="/login">Sign in instead</Link>
        </section>
      ) : (
        <JoinPanel view={view} signedInAs={emailFromToken(access)} />
      )}
    </main>
  )
}
