import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { TeamBoard } from './TeamBoard'
import type { Invited, Member, RoleCatalogue } from './types'

export const dynamic = 'force-dynamic'

/**
 * Team (Capability Universe §7.2–§7.3; Business OS Guide §5): who works here,
 * the role each person holds, where they work, and people added who have not
 * joined yet. A role is permissions + scope + the home they land on.
 */
export default async function TeamPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/v1/platform/businesses/${params.businessId}`
  const [teamRes, rolesRes] = await Promise.all([
    apiTry<{ data: { members: Member[]; invited: Invited[] } }>(`${base}/team`, token),
    apiTry<{ data: RoleCatalogue }>(`${base}/roles`, token),
  ])
  if (!teamRes.ok) {
    return (
      <div className="bos-page">
        <PageHeader title="Team" />
        <GateNotice error={teamRes.error} businessId={params.businessId} moduleLabel="Team" />
      </div>
    )
  }
  const { members, invited } = teamRes.data.data
  const roles = rolesRes.ok ? rolesRes.data.data : null
  return (
    <div className="bos-page">
      <PageHeader
        title="Team"
        subtitle="Who works here, what each person can do and where. Each role decides what they see when they sign in."
        actions={
          <>
            <Link className="btn-quiet" href={`/b/${params.businessId}/team/roles`}>
              Roles
            </Link>
            <Link className="btn" href={`/b/${params.businessId}/team/add`}>
              Add a person
            </Link>
          </>
        }
      />
      <TeamBoard businessId={params.businessId} members={members} invited={invited} roles={roles} />
    </div>
  )
}
